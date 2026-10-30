# Reads a stability CSV (batch,month,value) and prints expirest's poolability decision and shelf life as JSON.
# Usage: Rscript q1e.R data.csv spec_limit [lower|upper]
suppressMessages(library(expirest))
args <- commandArgs(trailingOnly = TRUE)
d <- read.csv(args[1], stringsAsFactors = FALSE)
d$batch <- factor(d$batch)
spec <- as.numeric(args[2])
side <- if (length(args) >= 3) args[3] else "lower"
r <- expirest_osle(data = d, response_vbl = "value", time_vbl = "month", batch_vbl = "batch",
                   sl = spec, sl_sf = 3, srch_range = c(0, 500), alpha = 0.05, alpha_pool = 0.25,
                   ivl_side = side)
acr <- r$Model.Type$type.acronym
# one batch: expirest has no poolability step, only the single-line ("dids") answer
decision <- switch(acr, cics = "fully pooled", dics = "common slope, separate intercepts",
                   dids = "separate", "single batch")
key <- if (acr == "n.a.") "dids" else acr
shelf <- unname(r$POI[key])  # worst case (earliest) over batches for the chosen model
per <- r$All.POI[[side]][[key]]
per_json <- if (length(per) > 1) {
  paste0("{", paste(sprintf("\"%s\": %.10f", names(per), per), collapse = ", "), "}")
} else "{}"
cat(sprintf("{\"acronym\": \"%s\", \"decision\": \"%s\", \"shelf\": %.10f, \"per_batch\": %s}\n",
            acr, decision, shelf, per_json))
