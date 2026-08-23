library(DatabaseConnector)
library(DataQualityDashboard)

args <- commandArgs(trailingOnly = TRUE)
ds_id <- if (length(args) > 0) args[1] else "nhanes-demo"
cdm_source_name <- if (length(args) > 1) args[2] else ds_id
cdm_schema <- if (length(args) > 2) args[3] else "public"  # NEW: 3rd optional arg, defaults to "public" so all existing calls (NHANES) are unaffected

connectionDetails <- createConnectionDetails(
  dbms         = "postgresql",
  server       = "localhost/omop",
  port         = 5433,
  user         = "omop_user",
  password     = "omop_pass",
  pathToDriver = "/Volumes/T7 Shield/ASDN Project/open-healthcare-dataset-explorer/jdbc"
)

DataQualityDashboard::executeDqChecks(
  connectionDetails      = connectionDetails,
  cdmDatabaseSchema      = cdm_schema,
  resultsDatabaseSchema  = cdm_schema,
  cdmSourceName          = cdm_source_name,
  numThreads             = 1,
  sqlOnly                = FALSE,
  outputFolder           = "dqd/raw",
  outputFile             = paste0(ds_id, ".json"),
  verboseMode            = FALSE,
  writeToTable           = FALSE
)

cat("\nDQD complete:", paste0("dqd/raw/", ds_id, ".json"), "\n")
cat("Schema checked:", cdm_schema, "\n")
