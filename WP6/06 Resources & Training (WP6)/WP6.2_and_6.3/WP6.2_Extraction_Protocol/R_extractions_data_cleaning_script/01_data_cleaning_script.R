####### Cleaning & Filtering Script
# Updated: 2026-07
# Protocol: v1.7 (see ARDC_6_2_Search_Protocol_v1_7.docx §12.1)
# Source data: compiled_reextraction_batches.xlsx (ARDC_6.2 repo)
#   - course_tools sheet now includes learning_needs_domain — taxonomy lookup no longer required
# Outputs:
#   6.4_cleaned_extraction_data.csv          <- consumed by dashboard.qmd
#   6.4_filtered_training_resources_data.csv <- full selected rows
#   6.4_course_tools_long_format_all.csv     <- all tool rows (no course filter)
#   6.4_course_tools_long_format_filtered.csv <- tool rows for selected courses

library(readxl)
library(tidyverse)
library(readxl)
library(dplyr)
library(tidyr)
library(readr)
library(stringr)



# ── Paths (update to match your local directory structure) ────────────────────
path_xlsx <- "C:/Users/robertj9/Repos/ARDC_6.2/08_reextraction/compiled_reextraction_batches.xlsx"
path_out  <- "C:/Users/robertj9/Repos/ARDC_6.4/01_data"

# =============================================================================
# NORMALISATION FUNCTIONS
# =============================================================================

normalize_format <- function(x) {
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xi <- trimws(xi)
    xl <- tolower(xi)
    if (grepl("short course|short_course|^course$|free course", xl)) return("Short Course")
    if (grepl("mooc", xl))                              return("MOOC")
    if (grepl("workshop", xl))                          return("Workshop")
    if (grepl("speciali[sz]ation", xl))                 return("Specialization")
    if (grepl("professional cert", xl))                 return("Prof. Certificate")
    if (grepl("webinar", xl))                           return("Webinar")
    if (grepl("interactive|text.*coding|tutorial", xl)) return("Interactive")
    if (grepl("video", xl))                             return("Video Course")
    return("Other")
  }, character(1))
}

normalize_cost <- function(x) {
  # Works on the new cost_model field (v1.7 protocol)
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xl <- tolower(trimws(xi))
    if (xl == "free")                                        return("Free")
    if (grepl("^free to audit", xl))                         return("Free to Audit")
    if (grepl("freemium|free trial|partial free", xl))       return("Freemium")
    if (grepl("institutional", xl))                          return("Institutional")
    if (grepl("subscription|maven pro", xl))                 return("Subscription")
    if (xl == "paid" || grepl("^paid", xl))                  return("Paid")
    return("Other")
  }, character(1))
}

normalize_language <- function(x) {
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xi <- trimws(xi)
    xl <- tolower(xi)
    if (xl %in% c("no programming", "conceptual", "methods",
                  "terminal", "english"))                    return("No Programming")
    if (xl == "python")                                      return("Python")
    if (xl == "r")                                           return("R")
    if (xl == "sql")                                         return("SQL")
    if (xl %in% c("multiple", "python, r", "r, python",
                  "python, sql", "r, sql", "python, r, sql",
                  "r, stata", "r, python"))                  return("Mixed")
    if (xl == "julia")                                       return("Julia")
    if (xl == "sas")                                         return("SAS")
    if (xl == "matlab")                                      return("MATLAB")
    return("Other")
  }, character(1))
}

normalize_health <- function(x) {
  # Handles health_domain_relevance (renamed from health_research_context in v1.7)
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "", "Not stated on course page",
                                "Not covered"))              return("Unknown")
    xl <- tolower(trimws(xi))
    if (xl == "no")                                          return("No")
    if (grepl("yes.{0,5}high|high.{0,5}yes", xl))           return("High")
    if (grepl("yes.{0,5}(medium|moderate)|(medium|moderate).{0,5}yes", xl)) return("Medium")
    if (grepl("yes.{0,5}low|low.{0,5}yes", xl))             return("Low")
    if (grepl("^yes", xl))                                   return("Yes")
    if (nchar(xi) > 40)                                      return("Yes")
    return("No")
  }, character(1))
}

normalize_research <- function(x) {
  # v1.7: Yes - Low added as a 4th value (was High / Moderate / No only)
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xi <- trimws(xi)
    if (xi %in% c("Yes - High", "Yes"))    return("High")
    if (xi == "Yes - Moderate")            return("Moderate")
    if (xi %in% c("Yes - Low", "Yes - Light", "Low")) return("Low")
    if (xi == "No")                        return("No")
    return("Unknown")
  }, character(1))
}

normalize_platform <- function(x) {
  # v1.7: exact casing enforced — Online / In-person / Blended only
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xl <- tolower(trimws(xi))
    if (xl %in% c("online", "coursera"))   return("Online")
    if (xl == "blended")                   return("Blended")
    if (grepl("in.person", xl))            return("In-person")
    # Combined values (e.g. "In-person / online") → Blended per v1.7
    if (grepl("/|and|&", xl))              return("Blended")
    return("Other")
  }, character(1))
}

normalize_pace <- function(x) {
  # v1.7: Mentor-led now formally in controlled vocab
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Unknown")
    xl <- tolower(trimws(xi))
    if (grepl("self.paced", xl))                      return("Self-paced")
    if (grepl("instructor.paced|instructor.led", xl)) return("Instructor-paced")
    if (grepl("cohort", xl))                          return("Cohort-based")
    if (grepl("hybrid", xl))                          return("Hybrid")
    if (grepl("bootcamp|intensive", xl))              return("Intensive")
    if (grepl("mentor", xl))                          return("Mentor-led")
    return("Other")
  }, character(1))
}

normalize_hands_on <- function(x) {
  # v1.7: bare Yes/No/unknown/Limited are ambiguous — flagged rather than dropped
  vapply(x, function(xi) {
    if (is.na(xi) || tolower(trimws(xi)) %in% c("na", "", "unknown")) return("Unknown")
    xl <- tolower(trimws(xi))
    if (grepl("extensive", xl))                return("Extensive")
    if (grepl("moderate", xl))                 return("Moderate")
    if (grepl("light", xl))                    return("Light")
    if (grepl("conceptual|no -|no–|no$", xl)) return("Conceptual / No coding")
    if (xl == "yes")                           return("Yes (level unspecified)")
    if (xl == "limited")                       return("Yes (level unspecified)")
    return("Unknown")
  }, character(1))
}

normalize_enrolment <- function(x) {
  # New field in v1.7 — normalises em dash vs hyphen variants
  vapply(x, function(xi) {
    if (is.na(xi) || xi %in% c("NA", "")) return("Not stated")
    xi <- trimws(xi)
    xl <- tolower(xi)
    if (grepl("open enrolment|^open$", xl))            return("Open enrolment")
    if (grepl("cohort.*(open)", xl))                   return("Scheduled cohort — open")
    if (grepl("cohort.*(closed)", xl))                 return("Scheduled cohort — closed")
    if (grepl("one.time.*passed|passed", xl))          return("One-time event — passed")
    if (grepl("not stated", xl))                       return("Not stated")
    return("Not stated")
  }, character(1))
}

normalize_weekly_time <- function(x) {
  # v1.7: bucket free-text into 5 controlled categories
  buckets <- c("< 1hr", "1-3 hrs", "3-5 hrs", "5-10 hrs", "10+ hrs")
  vapply(x, function(xi) {
    if (is.na(xi) || trimws(xi) == "") return(NA_character_)
    xi <- trimws(xi)
    if (xi %in% buckets) return(xi)   # already bucketed
    # extract first number for heuristic bucketing
    nums <- suppressWarnings(as.numeric(regmatches(xi, gregexpr("[0-9]+\\.?[0-9]*", xi))[[1]]))
    if (length(nums) == 0) return(NA_character_)
    lo <- min(nums)
    if (lo < 1)  return("< 1hr")
    if (lo < 3)  return("1-3 hrs")
    if (lo < 5)  return("3-5 hrs")
    if (lo < 10) return("5-10 hrs")
    return("10+ hrs")
  }, character(1))
}

normalize_qualification <- function(x) {
  # v1.7 direct value mapping (§5 of changelog)
  lookup <- c(
    "Nanodegree (certificate)"    = "Certificate",
    "Certificate (accredited)"    = "Certificate",
    "Completion certificate"      = "Certificate",
    "Course Certificate (Coursera)" = "Certificate",
    "Professional Certificate"    = "Certificate",
    "CPD points"                  = "Other"
  )
  vapply(x, function(xi) {
    if (is.na(xi) || trimws(xi) == "") return(NA_character_)
    xi <- trimws(xi)
    if (xi %in% names(lookup)) return(unname(lookup[xi]))
    xi  # already valid controlled-vocab value
  }, character(1))
}

normalize_duration <- function(x) {
  # v1.7: collapse blank-equivalent strings to true blank
  blank_equiv <- c("Not stated", "Not specified", "N/A", "NA", "Unknown",
                   "Not available", "TBC", "TBD", "")
  vapply(x, function(xi) {
    if (is.na(xi) || trimws(xi) %in% blank_equiv) return(NA_character_)
    trimws(xi)
  }, character(1))
}

# =============================================================================
# COURSEWORK RESOURCES
# =============================================================================

# ── Step 1: Load and filter selected courses ───────────────────────────────────
training_resources <- read_excel(path_xlsx, sheet = "coursework_resources") |>
  mutate(select_reject = str_remove_all(select_reject, " ")) |>
  filter(select_reject %in% c("select", "select?", "?")) |>
  mutate(select_reject = as.factor(select_reject))

training <- training_resources

write_csv(training_resources, file.path(path_out, "6.4_filtered_training_resources_data.csv"))

# =============================================================================
# COURSE TOOLS
# =============================================================================

# ── Step 2: Load course_tools (v1.7: learning_needs_domain pre-populated) ─────
course_tools_clean <- read_excel(path_xlsx, sheet = "course_tools") |>
  mutate(
    learning_need_tool    = str_trim(learning_need_tool),
    learning_needs_domain = str_trim(learning_needs_domain)
  ) |>
  filter(!is.na(learning_needs_domain), learning_needs_domain != "") |>
  distinct(course_id, learning_need_tool, .keep_all = TRUE)

write_csv(course_tools_clean, file.path(path_out, "6.4_course_tools_long_format_all.csv"))

# ── Step 3: Filter to selected courses only ────────────────────────────────────
course_tools_long_format <- course_tools_clean |>
  filter(course_id %in% training$course_id)

write_csv(course_tools_long_format, file.path(path_out, "6.4_course_tools_long_format_filtered.csv"))

# =============================================================================
# CLEANED EXTRACTION DATA (for dashboard)
# =============================================================================

# ── Collapse domains and tools per course into semicolon-separated strings ─────
domain_summary <- course_tools_long_format |>
  group_by(course_id) |>
  summarise(
    tool_domains = paste(sort(unique(learning_needs_domain)), collapse = "; "),
    tools_list   = paste(sort(unique(learning_need_tool)),   collapse = "; "),
    .groups = "drop"
  )

# ── Merge, normalise, and write dashboard-ready CSV ───────────────────────────
cleaned_extraction <- training_resources |>
  left_join(domain_summary, by = "course_id") |>
  transmute(
    # ── Identity
    id                       = course_id,
    course_name              = ifelse(is.na(course_name), "Untitled", course_name),
    link                     = ifelse(is.na(link), "", link),
    provider                 = ifelse(is.na(provider), "Unknown", provider),
    country                  = ifelse(is.na(country), "Unknown", country),

    # ── Course attributes
    level                    = ifelse(is.na(level) | level == "NA", "Unknown", level),
    format                   = normalize_format(format),
    delivery_platform        = normalize_platform(delivery_platform),
    learning_pace            = normalize_pace(learning_pace),
    duration                 = normalize_duration(duration),
    weekly_time_commitment   = normalize_weekly_time(weekly_time_commitment),
    enrolment_status         = normalize_enrolment(enrolment_status),
    next_start_date          = ifelse(
                                 enrolment_status == "Scheduled cohort — open" & !is.na(next_start_date),
                                 as.character(next_start_date), NA_character_
                               ),

    # ── Cost / access (v1.7: cost_model replaces cost_access)
    cost_model               = normalize_cost(cost_model),
    price_lowest_USD         = ifelse(is.na(price_lowest_USD), NA_real_, price_lowest_USD),
    price_certificate_USD    = ifelse(is.na(price_certificate_USD), NA_real_, price_certificate_USD),
    access_notes             = ifelse(is.na(access_notes), "", access_notes),

    # ── Relevance (v1.7 renames + new Yes-Low value)
    health_domain_relevance  = normalize_health(health_domain_relevance),
    research_workflow_relevance = normalize_research(research_workflow_relevance),

    # ── Skills / tools
    primary_language         = normalize_language(primary_language),
    primary_tools            = ifelse(is.na(primary_tools), "", primary_tools),
    tools_list               = ifelse(is.na(tools_list), "", tools_list),
    tool_domains             = ifelse(is.na(tool_domains), "", tool_domains),

    # ── Coding / AI fields
    hands_on_coding          = normalize_hands_on(hands_on_coding),
    API_integration          = ifelse(is.na(API_integration), "", API_integration),
    ethics_AI_safety         = ifelse(is.na(ethics_AI_safety), "", ethics_AI_safety),

    # ── Credential / eligibility
    qualification            = normalize_qualification(qualification),
    prerequisites            = case_when(
                                 is.na(prerequisites)                          ~ NA_character_,
                                 tolower(trimws(prerequisites)) %in%
                                   c("none stated", "n/a", "not stated", "")  ~ NA_character_,
                                 TRUE                                          ~ trimws(prerequisites)
                               ),

    # ── Descriptive text
    key_topics               = ifelse(is.na(key_topics), "", key_topics),
    target_audience          = ifelse(is.na(target_audience), "", target_audience),
    notes                    = ifelse(is.na(notes), "", notes),

    # ── Flags
    ARDC_audited             = ifelse(is.na(ARDC_audited), FALSE, ARDC_audited),
    duplicate_flag           = ifelse(is.na(duplicate_flag), FALSE, duplicate_flag),
    no_longer_maintained     = ifelse(is.na(no_longer_maintained), FALSE, no_longer_maintained),
    course_of_interest       = ifelse(is.na(course_of_interest), FALSE, course_of_interest),
  )

write_csv(cleaned_extraction, file.path(path_out, "6.4_cleaned_extraction_data.csv"))

# =============================================================================
# VERIFICATION SUMMARY
# =============================================================================
message("\n── Verification ─────────────────────────────────────────────────────────")
message("Selected courses: ", nrow(training))
message("All course-tool rows (clean): ", nrow(course_tools_clean))
message("Selected course-tool rows: ", nrow(course_tools_long_format))
message("Unique tools (filtered): ", n_distinct(course_tools_long_format$learning_need_tool))
message("Unique domains (filtered): ", n_distinct(course_tools_long_format$learning_needs_domain))

message("\nDomain counts (filtered) — should show 6 canonical domains:")
course_tools_long_format |>
  count(learning_needs_domain, name = "n_rows") |>
  arrange(learning_needs_domain) |>
  print()

message("\nNormalised value counts for key dashboard fields:")
cleaned_extraction |>
  select(level, format, delivery_platform, learning_pace, enrolment_status,
         health_domain_relevance, primary_language, cost_model,
         research_workflow_relevance, hands_on_coding, weekly_time_commitment,
         qualification) |>
  summarise(across(everything(), ~list(table(., useNA = "ifany")))) |>
  pivot_longer(everything(), names_to = "field", values_to = "counts") |>
  rowwise() |>
  mutate(summary = paste(names(counts), counts, sep = "=", collapse = ", ")) |>
  select(field, summary) |>
  print(n = Inf)

message("\nRows with ambiguous hands_on_coding (may need re-extraction): ",
  sum(cleaned_extraction$hands_on_coding == "Yes (level unspecified)", na.rm = TRUE))

message("Rows sourced from fallback (flagged in notes): ",
  sum(grepl("blocked|fallback|Class Central|wayback|robots\\.txt",
            cleaned_extraction$notes, ignore.case = TRUE)))

source(file.path(path_out, "validate_outputs.R"))

