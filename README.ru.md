# Career Radar

[English version](README.md)

Evidence-first локальная карьерная аналитика. Проект превращает проверяемые проектные артефакты в детерминированный vacancy matching, аргументы для отклика и roadmap развития без выдумывания опыта.

## Проблема

- Проектные доказательства, навыки и требования вакансий обычно разбросаны по заметкам, репозиториям и описаниям вакансий.
- Ручной разбор вакансий занимает время и легко приводит к слабым совпадениям.
- Приватные карьерные факты нельзя хранить в Git, но matching всё равно должен учитывать структурированные ограничения.

## Стек

- Python 3.11+
- FastAPI + Uvicorn для локальной панели
- SQLite для приватного Opportunity Inbox
- PyYAML для evidence, goals и matching config
- unittest + локальные deterministic fixtures

## Setup

```bash
git clone https://github.com/xelvhk/career-radar.git
cd career-radar
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/validate_data.py
.venv/bin/python -m unittest discover -s tests -v
```

Опциональный приватный профиль:

```bash
cp career_profile.local.example.yaml career_profile.local.yaml
```

`career_profile.local.yaml` и локальная SQLite-база Inbox игнорируются Git.

## Архитектура

```text
YAML evidence layer
  skills.yaml, projects.yaml, career_goals.yaml, matching.yaml, search_profiles.yaml

Matching layer
  career_radar/matching.py, matching_config.py, validation.py

Opportunity Inbox
  opportunity_store.py, opportunity_service.py, scripts/inbox.py

Local panel
  career_radar/panel.py, scripts/run_panel.py

Source adapters
  hh_source.py, scan_service.py, source_audit.py
```

Matcher работает детерминированно и offline. Source adapters должны fail closed, если локальная конфигурация неполная.

## Demo

Проверить evidence и matching rules:

```bash
python3 scripts/validate_data.py
python3 scripts/list_search_queries.py
```

Сопоставить одну сохранённую вакансию:

```bash
python3 scripts/match_vacancy.py vacancy.txt
python3 scripts/match_vacancy.py vacancy.txt --format json
```

Запустить локальную панель:

```bash
python3 scripts/run_panel.py --profile career_profile.local.yaml
```

Откройте `http://127.0.0.1:8765`.

## Граница приватности

- Полный текст вакансий остаётся в локальной SQLite-базе, которая игнорируется Git.
- Приватные данные профиля остаются в `career_profile.local.yaml`.
- В репозитории хранятся публичные evidence, sanitized fixtures и source-neutral конфигурация.

## Roadmap

- [ ] Улучшить explanations для evidence scoring в локальной панели.
- [ ] Добавить экспортируемые Markdown-отчёты для shortlisted opportunities.
- [ ] Расширить source adapters с сохранением fail-closed проверок конфигурации.

## Статус

Active development

## Лицензия

Лицензия пока не указана.
