DROP TABLE IF EXISTS sentinel.knowledge_documents;

CREATE TABLE IF NOT EXISTS sentinel.knowledge_documents (
    source_id String,
    generation UUID,
    object_key String,
    domains Array(String),
    repository LowCardinality(String),
    source_revision String,
    content_hash String,
    index_signature String,
    content String,
    version UInt64,
    is_deleted UInt8,
    indexed_at DateTime64(6, 'UTC')
) ENGINE = ReplacingMergeTree(version)
ORDER BY source_id;

DROP TABLE IF EXISTS sentinel.knowledge_chunks;

CREATE TABLE IF NOT EXISTS sentinel.knowledge_chunks (
    source_id String,
    generation UUID,
    chunk_number UInt32,
    object_key String,
    content String,
    embedding Array(Float32),
    CONSTRAINT embedding_dimensions CHECK length(embedding) = 768,
    INDEX embedding_hnsw embedding TYPE vector_similarity('hnsw', 'cosineDistance', 768)
) ENGINE = MergeTree
ORDER BY (source_id, generation, chunk_number);
