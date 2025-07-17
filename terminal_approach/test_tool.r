myfunc <- function(x) x*2
args <- commandArgs(trailingOnly=TRUE)
res <- myfunc(as.numeric(args[1]))
cat(res)
print(res)