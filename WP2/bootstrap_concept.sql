-- bootstrap_concept.sql
--
-- TEMPORARY placeholder rows to unblock ETL work while the concept
-- table is empty (standard OMOP vocabulary not yet loaded).
--
-- concept/domain/vocabulary/concept_class have a circular FK
-- dependency: concept.domain_id -> domain(domain_id), but
-- domain.domain_concept_id -> concept(concept_id), and likewise for
-- vocabulary/concept_class. This script temporarily DROPS the six FK
-- constraints that form the cycle, inserts a minimal self-referential
-- bootstrap set, then ADDS the constraints back -- rather than
-- disabling triggers.
--
-- IMPORTANT: these are placeholder rows, not the real OHDSI standard
-- vocabulary. Before loading the actual CONCEPT.csv/DOMAIN.csv/etc.
-- from Athena (https://athena.ohdsi.org/), DELETE these rows first --
-- they will collide on primary key with the real vocabulary's rows
-- for the same IDs.
--
-- Runs as a single transaction: if anything fails, everything rolls
-- back and your schema is left exactly as it was.

BEGIN;

-- Drop the six constraints forming the circular dependency
ALTER TABLE concept DROP CONSTRAINT fpk_concept_domain_id;
ALTER TABLE concept DROP CONSTRAINT fpk_concept_vocabulary_id;
ALTER TABLE concept DROP CONSTRAINT fpk_concept_concept_class_id;
ALTER TABLE domain DROP CONSTRAINT fpk_domain_domain_concept_id;
ALTER TABLE vocabulary DROP CONSTRAINT fpk_vocabulary_vocabulary_concept_id;
ALTER TABLE concept_class DROP CONSTRAINT fpk_concept_class_concept_class_concept_id;

-- Bootstrap domain/vocabulary/concept_class rows needed by concept_id=0
INSERT INTO domain (domain_id, domain_name, domain_concept_id)
VALUES ('Metadata', 'Metadata', 0)
ON CONFLICT (domain_id) DO NOTHING;

INSERT INTO vocabulary (vocabulary_id, vocabulary_name, vocabulary_reference, vocabulary_concept_id)
VALUES ('None', 'OMOP Standard Vocabulary (placeholder)', 'placeholder -- no real vocabulary loaded', 0)
ON CONFLICT (vocabulary_id) DO NOTHING;

INSERT INTO concept_class (concept_class_id, concept_class_name, concept_class_concept_id)
VALUES ('Undefined', 'Undefined', 0)
ON CONFLICT (concept_class_id) DO NOTHING;

-- concept_id = 0: the standard OMOP "no matching concept" sentinel,
-- used throughout your ETL scripts for unmapped fields.
INSERT INTO concept (
    concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
    standard_concept, concept_code, valid_start_date, valid_end_date, invalid_reason
) VALUES (
    0, 'No matching concept', 'Metadata', 'None', 'Undefined',
    NULL, 'No matching concept', '1970-01-01', '2099-12-31', NULL
) ON CONFLICT (concept_id) DO NOTHING;

-- Gender concepts, matching the values already used by your existing
-- NHANES person data (8507 = MALE, 8532 = FEMALE, real OHDSI standard
-- concept IDs).
INSERT INTO domain (domain_id, domain_name, domain_concept_id)
VALUES ('Gender', 'Gender', 0)
ON CONFLICT (domain_id) DO NOTHING;

INSERT INTO vocabulary (vocabulary_id, vocabulary_name, vocabulary_reference, vocabulary_concept_id)
VALUES ('Gender', 'OMOP Gender (placeholder)', 'placeholder -- no real vocabulary loaded', 0)
ON CONFLICT (vocabulary_id) DO NOTHING;

INSERT INTO concept_class (concept_class_id, concept_class_name, concept_class_concept_id)
VALUES ('Gender', 'Gender', 0)
ON CONFLICT (concept_class_id) DO NOTHING;

INSERT INTO concept (
    concept_id, concept_name, domain_id, vocabulary_id, concept_class_id,
    standard_concept, concept_code, valid_start_date, valid_end_date, invalid_reason
) VALUES
    (8507, 'MALE', 'Gender', 'Gender', 'Gender', 'S', 'M', '1970-01-01', '2099-12-31', NULL),
    (8532, 'FEMALE', 'Gender', 'Gender', 'Gender', 'S', 'F', '1970-01-01', '2099-12-31', NULL)
ON CONFLICT (concept_id) DO NOTHING;

-- Add the six constraints back
ALTER TABLE concept ADD CONSTRAINT fpk_concept_domain_id
    FOREIGN KEY (domain_id) REFERENCES domain(domain_id);
ALTER TABLE concept ADD CONSTRAINT fpk_concept_vocabulary_id
    FOREIGN KEY (vocabulary_id) REFERENCES vocabulary(vocabulary_id);
ALTER TABLE concept ADD CONSTRAINT fpk_concept_concept_class_id
    FOREIGN KEY (concept_class_id) REFERENCES concept_class(concept_class_id);
ALTER TABLE domain ADD CONSTRAINT fpk_domain_domain_concept_id
    FOREIGN KEY (domain_concept_id) REFERENCES concept(concept_id);
ALTER TABLE vocabulary ADD CONSTRAINT fpk_vocabulary_vocabulary_concept_id
    FOREIGN KEY (vocabulary_concept_id) REFERENCES concept(concept_id);
ALTER TABLE concept_class ADD CONSTRAINT fpk_concept_class_concept_class_concept_id
    FOREIGN KEY (concept_class_concept_id) REFERENCES concept(concept_id);

COMMIT;

-- Verify
SELECT concept_id, concept_name, domain_id, vocabulary_id FROM concept ORDER BY concept_id;
