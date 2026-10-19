# Smoke tests (R side), reference only. Run from the Assessment root: Rscript reference/smoke/smoke_tests.R
# Uses the eval/ renv library.
# Recomputes Fig 4B correlations, Fig 7A ANOVA, Fig 6C t-tests from sheet H, and fgsea for one
# program from sdt4, mirroring the paper's code (reference/functions).
renv::load("eval")
suppressPackageStartupMessages({library(dplyr); library(rstatix); library(fgsea); library(msigdbr)})
d <- "JCI_data/jci.insight.176963.sdval_"; out <- "reference/smoke/out/"; dir.create(out, showWarnings = FALSE)
H <- read.csv(paste0(d, "H.csv"), check.names = FALSE)
grp <- read.csv(paste0(d, "Fig7B.csv"))[, c("Paper_ID", "DA_group", "case_ctrl")]
X <- H[, -(1:2)]; rownames(X) <- H$Paper_ID

# 1. Fig 4B: Pearson correlation of per-sample program scores
f4 <- read.csv(paste0(d, "Fig4B.csv"), skip = 1, row.names = 1, check.names = FALSE, na.strings = "#N/A")
r <- cor(X)[rownames(f4), colnames(f4)]; diag(r) <- NA
cat(sprintf("[Fig4B] programs=%d  max|cor(H) - Fig4B| = %.2e\n", nrow(f4), max(abs(r - as.matrix(f4)), na.rm = TRUE)))

# 2. Fig 7A / 6C: same tests as Calculate_metadata_associations (rstatix anova_test ges; t_test)
df <- cbind(grp[match(rownames(X), grp$Paper_ID), ], X)
colnames(df) <- gsub("[-.]", "_", colnames(df))
progs <- setdiff(colnames(df), colnames(grp))
anova <- bind_rows(lapply(progs, function(p) {
  a <- anova_test(df, as.formula(paste(p, "~ DA_group")))
  data.frame(program = p, eta2 = a$ges, p_value = a$p)}))
ttest <- bind_rows(lapply(progs, function(p) {
  t <- t_test(df, as.formula(paste(p, "~ case_ctrl")), ref.group = "JDM", detailed = TRUE)
  data.frame(program = p, estimate = t$estimate, p_value = t$p)}))
write.csv(anova, paste0(out, "anova_DA_group.csv"), row.names = FALSE)
write.csv(ttest, paste0(out, "ttest_case_ctrl.csv"), row.names = FALSE)
cat(sprintf("[Fig7A/6C] ANOVA + t-test on %d programs, groups: %s\n", length(progs),
            paste(names(table(df$DA_group)), table(df$DA_group), sep = "=", collapse = " ")))

# 3. fgsea for one program, settings from fgsea_test(); GO:BP from msigdbr 7.5.1 (C5)
m <- read.csv("JCI_data/jci.insight.176963.sdt4_Bcells.csv", check.names = FALSE)
stats <- setNames(as.numeric(m$R17_Program6), m$genes)
go <- msigdbr(species = "Homo sapiens", category = "C5", subcategory = "GO:BP")
paths <- split(go$gene_symbol, go$gs_name)
set.seed(1)
res <- fgsea(pathways = paths, stats = stats, minSize = 10, maxSize = Inf, eps = 1e-50, nPermSimple = 100000)
res$leadingEdge <- vapply(res$leadingEdge, paste, "", collapse = ", ")
write.csv(res, paste0(out, "fgsea_Bcells_R17_Program6.csv"), row.names = FALSE)
cat(sprintf("[fgsea] msigdbr %s: %d GO:BP sets; %d tested for Bcells R17_Program6\n",
            packageVersion("msigdbr"), length(paths), nrow(res)))
