
myfunc <- function(...) {
    x <- c(...)
    x * 2
}
args <- commandArgs(trailingOnly=TRUE)
nums <- as.numeric(args)
res <- sapply(nums, myfunc)
cat(res, sep = " ")
print(res)