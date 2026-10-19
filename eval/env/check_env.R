# analysis-env — load every package and print versions. Run from project root: Rscript env/check_env.R
pkgs <- sub("^library\\((.*)\\)$", "\\1", readLines("env/dependencies.R"))
cat(R.version.string, "| renv", as.character(packageVersion("renv")),
    "| Bioc", as.character(BiocManager::version()), "\n")
cat("libPaths:", .libPaths()[1], "\n")
ok <- vapply(pkgs, function(p) suppressPackageStartupMessages(requireNamespace(p, quietly = TRUE)), logical(1))
for (p in pkgs) cat(sprintf("  %-16s %s\n", p, if (ok[[p]]) as.character(packageVersion(p)) else "MISSING"))
if (!all(ok)) stop("Missing packages: ", paste(pkgs[!ok], collapse = ", "))
cat("All", length(pkgs), "R packages load.\n")
