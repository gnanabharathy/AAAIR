-- register_drug_exposure_concept.sql
--
-- The LLM-generated mapping for dsqfile1-1999's DSD010 variable
-- ("Any Dietary Supplements taken?") specifies drug_concept_id=380001
-- ("Dietary supplement") -- a real OHDSI standard concept_id from the
-- full RxNorm/SNOMED vocabulary that this CDM instance doesn't have
-- loaded (only a handful of bootstrap placeholder concepts exist so
-- far). This registers a minimal placeholder for it so
-- drug_exposure's foreign key constraint on drug_concept_id is
-- satisfied.
--
-- Same pattern as bootstrap_concept.sql's earlier placeholders
-- (concept_id 0/8507/8532) and register_vocab_metadata.py's
-- concept_id 4180186 (English language) for concept_synonym.

-- Ensure supporting domain/vocabulary/concept_class rows exist first.
INSERT INTO domain (domain_id, domain_name, domain_concept_id)
VALUES ('Drug', 'Drug', 0)
ON CONFLICT (domain_id) DO NOTHING;

INSERT INTO vocabulary (vocabulary_id, vocabulary_name, vocabulary_reference, vocabulary_version, vocabulary_concept_id)
VALUES ('RxNorm', 'RxNorm (placeholder -- full vocabulary not loaded)', 'https://www.nlm.nih.gov/research/umls/rxnorm/', 'placeholder', 0)
ON CONFLICT (vocabulary_id) DO NOTHING;

INSERT INTO concept_class (concept_class_id, concept_class_name, concept_class_concept_id)
VALUES ('Ingredient', 'Ingredient', 0)
ON CONFLICT (concept_class_id) DO NOTHING;

INSERT INTO concept (
    concept_id, concept_name, domain_id, vocabulary_id,
    concept_class_id, standard_concept, concept_code,
    valid_start_date, valid_end_date, invalid_reason
)
VALUES (
    380001, 'Dietary supplement', 'Drug', 'RxNorm',
    'Ingredient', NULL, '380001',
    '1970-01-01', '2099-12-31', NULL
)
ON CONFLICT (concept_id) DO NOTHING;

SELECT 'concept 380001 registered' AS status;
