BIB=content/bib/grad_methods.bib
SCHED_IN=content/schedule_bib.md
SCHED_OUT=content/schedule.md

expand:
	python build_schedule.py --in $(SCHED_IN) --out $(SCHED_OUT) --bib $(BIB) --start 2026-01-21

build: expand
	Rscript -e "blogdown::build_site()"