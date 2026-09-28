-- create_ptbxl_view_schema.sql
--
-- Creates an isolated schema (ptbxl_view) containing filtered views of
-- the 5 tables PTB-XL actually populated, plus empty passthrough views
-- for every other table the OHDSI DataQualityDashboard package expects
-- to find in a CDM schema. Point dqd.R's cdmDatabaseSchema at
-- 'ptbxl_view' instead of 'public' to get a DQD report scoped to just
-- PTB-XL, instead of the whole cumulative database.
--
-- Filter condition: person.year_of_birth = 9999 (the sentinel used by
-- etl_ptbxl_v2.py for all PTB-XL person rows -- NHANES rows have real
-- birth years, so this cleanly separates the two without touching any
-- NHANES data or scripts).
--
-- NOTE: if you later fix PTB-XL's year_of_birth to a real value, this
-- filter breaks. At that point, swap it for a person_id range filter
-- instead (regenerate this script with min/max person_id bounds).
--
-- Safe to re-run: DROP SCHEMA ... CASCADE at the top means this can be
-- regenerated fresh any time without manual cleanup.

DROP SCHEMA IF EXISTS ptbxl_view CASCADE;
CREATE SCHEMA ptbxl_view;

-- --- Populated tables: filtered views -------------------------------

CREATE VIEW ptbxl_view.person AS
    SELECT * FROM public.person
    WHERE year_of_birth = 9999;

CREATE VIEW ptbxl_view.measurement AS
    SELECT m.* FROM public.measurement m
    JOIN public.person p ON m.person_id = p.person_id
    WHERE p.year_of_birth = 9999;

CREATE VIEW ptbxl_view.observation AS
    SELECT o.* FROM public.observation o
    JOIN public.person p ON o.person_id = p.person_id
    WHERE p.year_of_birth = 9999;

CREATE VIEW ptbxl_view.condition_occurrence AS
    SELECT c.* FROM public.condition_occurrence c
    JOIN public.person p ON c.person_id = p.person_id
    WHERE p.year_of_birth = 9999;

CREATE VIEW ptbxl_view.note AS
    SELECT n.* FROM public.note n
    JOIN public.person p ON n.person_id = p.person_id
    WHERE p.year_of_birth = 9999;

-- --- Empty passthrough views for every other CDM table --------------
-- DataQualityDashboard's standard check set expects these tables to
-- exist even if a given data source never populates them. Empty
-- views satisfy that without pulling in any NHANES data.

CREATE VIEW ptbxl_view.death AS
    SELECT * FROM public.death WHERE false;

CREATE VIEW ptbxl_view.device_exposure AS
    SELECT * FROM public.device_exposure WHERE false;

CREATE VIEW ptbxl_view.dose_era AS
    SELECT * FROM public.dose_era WHERE false;

CREATE VIEW ptbxl_view.drug_era AS
    SELECT * FROM public.drug_era WHERE false;

CREATE VIEW ptbxl_view.drug_exposure AS
    SELECT * FROM public.drug_exposure WHERE false;

CREATE VIEW ptbxl_view.observation_period AS
    SELECT * FROM public.observation_period WHERE false;

CREATE VIEW ptbxl_view.payer_plan_period AS
    SELECT * FROM public.payer_plan_period WHERE false;

CREATE VIEW ptbxl_view.procedure_occurrence AS
    SELECT * FROM public.procedure_occurrence WHERE false;

CREATE VIEW ptbxl_view.specimen AS
    SELECT * FROM public.specimen WHERE false;

CREATE VIEW ptbxl_view.visit_detail AS
    SELECT * FROM public.visit_detail WHERE false;

CREATE VIEW ptbxl_view.visit_occurrence AS
    SELECT * FROM public.visit_occurrence WHERE false;

-- --- Reference/vocabulary tables: passed through unfiltered ---------
-- These are shared metadata (not patient data), not something to
-- isolate per-dataset -- DQD checks join against them.

CREATE VIEW ptbxl_view.concept AS SELECT * FROM public.concept;
CREATE VIEW ptbxl_view.concept_ancestor AS SELECT * FROM public.concept_ancestor;
CREATE VIEW ptbxl_view.concept_class AS SELECT * FROM public.concept_class;
CREATE VIEW ptbxl_view.concept_relationship AS SELECT * FROM public.concept_relationship;
CREATE VIEW ptbxl_view.concept_synonym AS SELECT * FROM public.concept_synonym;
CREATE VIEW ptbxl_view.domain AS SELECT * FROM public.domain;
CREATE VIEW ptbxl_view.drug_strength AS SELECT * FROM public.drug_strength;
CREATE VIEW ptbxl_view.relationship AS SELECT * FROM public.relationship;
CREATE VIEW ptbxl_view.vocabulary AS SELECT * FROM public.vocabulary;
CREATE VIEW ptbxl_view.source_to_concept_map AS SELECT * FROM public.source_to_concept_map;

-- --- Administrative tables: passed through unfiltered ----------------
-- Not patient-level data, no dataset-specific filtering needed.

CREATE VIEW ptbxl_view.care_site AS SELECT * FROM public.care_site;
CREATE VIEW ptbxl_view.cdm_source AS SELECT * FROM public.cdm_source;
CREATE VIEW ptbxl_view.cohort_definition AS SELECT * FROM public.cohort_definition;
CREATE VIEW ptbxl_view.cost AS SELECT * FROM public.cost;
CREATE VIEW ptbxl_view.fact_relationship AS SELECT * FROM public.fact_relationship;
CREATE VIEW ptbxl_view.location AS SELECT * FROM public.location;
CREATE VIEW ptbxl_view.metadata AS SELECT * FROM public.metadata;
CREATE VIEW ptbxl_view.note_nlp AS SELECT * FROM public.note_nlp;
CREATE VIEW ptbxl_view.provider AS SELECT * FROM public.provider;

-- Verify
SELECT table_name FROM information_schema.views WHERE table_schema = 'ptbxl_view' ORDER BY table_name;
