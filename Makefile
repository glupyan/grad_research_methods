BIB=content/bib/cogsci_llms_pruned.bib
SCHED_IN=content/schedule_bib.md
SCHED_OUT=content/schedule.md

expand:
	python build_schedule.py --in $(SCHED_IN) --out $(SCHED_OUT) --bib $(BIB) --start 2025-09-03

build: expand
	Rscript -e "blogdown::build_site()"