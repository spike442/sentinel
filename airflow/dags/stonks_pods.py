from datetime import datetime, timedelta

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.sdk import Param
from kubernetes.client import models as k8s

TIMEZONE = "Europe/Paris"
START_DATE = datetime(2026, 10, 1)
NAMESPACE = "{{ var.value.get('stonks_namespace', 'agents') }}"
REGISTRY = "{{ var.value.get('stonks_registry', 'ghcr.io/spike442/sentinel') }}"
VERSION = "{{ var.value.stonks_version }}"
TRADE_DATE = (
    "{{ params.trade_date or (logical_date or dag_run.run_after).in_timezone('"
    + TIMEZONE
    + "').strftime('%Y-%m-%d') }}"
)
SECRET = "stonks-secrets"
CONFIG_MAP = "stonks-config"
SERVICE_ACCOUNT = "stonks"
RUN_AS = 65532
S3_KEYS = ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")

PARAMS = {
    "trade_date": Param(
        "",
        type="string",
        description="Trade date as YYYY-MM-DD; empty uses the run's date in Europe/Paris.",
    )
}
DEFAULT_ARGS = {
    "owner": "stonks",
    "retries": 0,
    "retry_delay": timedelta(minutes=10),
}


def secret_env(keys: tuple[str, ...]) -> list[k8s.V1EnvVar]:
    return [
        k8s.V1EnvVar(
            name=key,
            value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name=SECRET, key=key)),
        )
        for key in keys
    ]


def config_volumes() -> tuple[list[k8s.V1Volume], list[k8s.V1VolumeMount]]:
    volumes = [
        k8s.V1Volume(name="config", config_map=k8s.V1ConfigMapVolumeSource(name=CONFIG_MAP)),
        k8s.V1Volume(name="tmp", empty_dir=k8s.V1EmptyDirVolumeSource()),
    ]
    mounts = [
        k8s.V1VolumeMount(name="config", mount_path="/etc/stonks", read_only=True),
        k8s.V1VolumeMount(name="tmp", mount_path="/tmp"),
    ]
    return volumes, mounts


def stonks_pod(task_id: str, module: str, *, secrets: tuple[str, ...], **kwargs) -> KubernetesPodOperator:
    volumes, mounts = config_volumes()
    environment = secret_env(secrets)
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"stonks-{module}-{task_id}",
        namespace=NAMESPACE,
        image=f"{REGISTRY}/stonks-{module}:{VERSION}",
        arguments=[task_id, "--trade-date", TRADE_DATE],
        env_vars=environment,
        volumes=volumes,
        volume_mounts=mounts,
        service_account_name=SERVICE_ACCOUNT,
        automount_service_account_token=False,
        security_context=k8s.V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=RUN_AS,
            run_as_group=RUN_AS,
            seccomp_profile=k8s.V1SeccompProfile(type="RuntimeDefault"),
        ),
        container_security_context=k8s.V1SecurityContext(
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities=k8s.V1Capabilities(drop=["ALL"]),
        ),
        container_resources=k8s.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "256Mi"},
            limits={"memory": "1Gi"},
        ),
        labels={"app.kubernetes.io/name": f"stonks-{module}", "app.kubernetes.io/part-of": "stonks"},
        image_pull_policy="IfNotPresent",
        get_logs=True,
        on_finish_action="delete_succeeded_pod",
        startup_timeout_seconds=600,
        **kwargs,
    )


def stonks_spark(task_id: str, **kwargs) -> SparkKubernetesOperator:
    return SparkKubernetesOperator(
        task_id=task_id,
        namespace=NAMESPACE,
        application_file="templates/stonks-spark.yaml",
        get_logs=True,
        delete_on_termination=True,
        **kwargs,
    )
