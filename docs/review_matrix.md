# Проверяемые границы реализации

| Граница | Реализация / доказательство |
|---|---|
| Источник покрытия | `coverage.py`; `test_coverage_rejects_foreign_source` |
| Отдельные экземпляры одинакового значения | `decoder.py`, `pipeline.py`; `test_contracts.py`, `test_replay.py` |
| Сессии и эпохи часов | `session.py`, `transport.py`; рестарты в `test_transport.py` |
| Актуальные числа PDF | `report_content.py`, `materials.py`; подмена входов в `test_materials.py` |
| Среда и ревизия | `provenance.py`; `metadata` каждого результата |
| Строгий WCS | `validate_message`; таблица противоречивых пакетов в тестах |
| Сквозная интеграция | `python -m barcode_reader.replay`; производственный контракт и SQLite |
| Общая конфигурация | `configs/conveyor.json`; `test_configuration.py` |
| Ограничение хранения | `Pipeline.prune`, `Outbox.prune`, `DurableWCS.prune`; 5000 треков |
| Расширенная нагрузка | `load_replay.py`: три запуска, углы, ухудшения, пустые кадры, 24 значения |
| Автоматическая проверка материалов | `.github/workflows/tests.yml`, `experiments.yml` |
| Оформление и зависимости | Ruff, группы core/report/test, исполненный Jupyter Notebook |

Оптика и механика обоснованы расчётами и схемами PDF. Промышленный HTTP-сервис, DMA/SDK, аппаратный watchdog и WCS–ПЛК handshake входят в программу физической приёмки.
