import { Block, KeyValues, TextList } from "../../../components/RecordSections";
import { ManualActionCard } from "./ManualActions";
import type { Diagnosis } from "./model";

export function DiagnosisView({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <div className="diagnosis">
      {diagnosis.hypothesis && <p className="diagnosis-hypothesis">{diagnosis.hypothesis}</p>}
      <KeyValues
        values={{
          status: diagnosis.status,
          incident: diagnosis.incident,
          risk: diagnosis.risk,
          confidence: diagnosis.confidence,
        }}
      />
      <h4>Evidence</h4>
      <TextList items={diagnosis.evidence} />
      <h4>Validation</h4>
      <TextList items={diagnosis.validation} />
      {diagnosis.rollback && (
        <>
          <h4>Rollback</h4>
          <p>{diagnosis.rollback}</p>
        </>
      )}
      {Boolean(diagnosis.proposed_files?.length) && (
        <>
          <h4>Proposed files</h4>
          <TextList items={diagnosis.proposed_files} />
        </>
      )}
      {(diagnosis.pr_title || diagnosis.pr_body) && (
        <>
          <h4>Pull request</h4>
          {diagnosis.pr_title && <p className="diagnosis-pr-title">{diagnosis.pr_title}</p>}
          {diagnosis.pr_body && <Block value={diagnosis.pr_body} />}
        </>
      )}
      {diagnosis.proposed_changes?.map((change) => (
        <details className="nested" key={change.file_path}>
          <summary>{change.delete ? `${change.file_path} (deleted)` : change.file_path}</summary>
          {!change.delete && <Block value={change.content} />}
        </details>
      ))}
      {Boolean(diagnosis.manual_actions?.length) && (
        <>
          <h4>Manual actions</h4>
          {diagnosis.manual_actions?.map((action, index) => (
            <ManualActionCard action={action} key={`${action.command}-${index}`} />
          ))}
        </>
      )}
    </div>
  );
}
