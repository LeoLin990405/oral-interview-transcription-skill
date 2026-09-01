SKILL := oral-history-master

.PHONY: test lint smoke help

help:
	@echo "make test   跑单元测试"
	@echo "make lint   语法检查 (py_compile)"
	@echo "make smoke  对 demo 跑 check，确认审阅包生成"

test:
	cd $(SKILL) && python3 -m unittest discover tests -v

lint:
	python3 -m py_compile $(SKILL)/scripts/*.py $(SKILL)/tests/*.py
	@echo "✓ py_compile OK"

smoke:
	cd $(SKILL)/scripts && python3 run_pipeline.py check demo
	test -f $(SKILL)/projects/demo/review/审阅稿.html
	test -f $(SKILL)/projects/demo/review/审阅稿.docx
	test -f $(SKILL)/projects/demo/review/对照稿.md
	@echo "✓ demo smoke OK"
