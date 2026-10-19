# jdm-fig7 — export Supplemental Table 4 (legacy .xls; per-cell-type marker gene scores) to CSV,
# one file per sheet: JCI_data/jci.insight.176963.sdt4_<CellType>.csv
p <- "JCI_data/jci.insight.176963.sdt4.xls"
for (s in readxl::excel_sheets(p)) {
  d <- readxl::read_excel(p, sheet = s, col_types = "text")  # text: keep full precision as stored
  f <- sprintf("JCI_data/jci.insight.176963.sdt4_%s.csv", gsub("[^A-Za-z0-9._-]+", "_", s))
  readr::write_csv(d, f, na = "")
  cat(sprintf("%-10s %5d genes x %2d programs -> %s\n", s, nrow(d), ncol(d) - 1, basename(f)))
}
