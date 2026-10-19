# analysis-env — first-time renv setup (only used by env/setup.sh when renv.lock is absent).
# Copies exact versions from the system R 4.2.3 library (renv::hydrate), installs anything missing
# from CRAN R-4.2 binaries / Bioconductor 3.16, then snapshots.
options(repos = c(CRAN = "https://cran.r-project.org"), pkgType = "both",
        install.packages.compile.from.source = "never")
pkgs <- sub("^library\\((.*)\\)$", "\\1", readLines("env/dependencies.R"))
bioc <- c("ComplexHeatmap", "fgsea", "BiocParallel", "clusterProfiler", "SingleCellExperiment", "scran",
          "scater", "scuttle", "limma", "edgeR", "DESeq2", "GSVA", "GSEABase", "AUCell", "batchelor", "bluster",
          "decoupleR", "dittoSeq", "MAST", "sva", "org.Hs.eg.db")
renv::init(bare = TRUE, settings = list(snapshot.type = "explicit"), restart = FALSE)
sys_lib <- normalizePath(file.path(R.home(), "library"))  # renv sandboxes .Library; use the real path
renv::hydrate(packages = pkgs, sources = sys_lib, prompt = FALSE)
missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  options(repos = BiocManager::repositories(version = "3.16"))
  utils::install.packages(setdiff(missing, bioc), lib = .libPaths()[1], type = "binary")
  if (any(missing %in% bioc)) BiocManager::install(intersect(missing, bioc), version = "3.16",
                                                   update = FALSE, ask = FALSE, type = "binary")
}
if (packageVersion("msigdbr") != "7.4.1") renv::install("msigdbr@7.4.1", prompt = FALSE)
renv::settings$bioconductor.version("3.16")
renv::snapshot(type = "explicit", prompt = FALSE, force = TRUE)
