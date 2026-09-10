# Шестистороннее чтение штрихкодов

Карим Гимадиев · Мастерская Ozon · Computer Vision, вариант 2.

[Итоговый PDF](output/pdf/ozon_cv2_report_ru.pdf) · [Jupyter Notebook](notebooks/demo_ru.ipynb) · [Инженерный контракт](docs/system_contract.md) · [Соответствие заданию](docs/audit.md)

Четыре линейные камеры сканируют верх, дно и бока; две площадные камеры снимают торцы. Энкодер связывает захват с движением. Локальный компьютер назначает обнаружения коробкам, объединяет значения и передаёт результат WCS.

![Схема наблюдения торцов](docs/figures/layout.png)

## Измеренные результаты

<!-- RESULTS:START -->
Результаты формируются командой `python scripts/update_readme.py` из журналов эксперимента.
<!-- RESULTS:END -->

Полные исходные данные: [номинальный эксперимент](results/nominal.json), [факторный эксперимент](results/ablation.json), [нагрузка](results/load_replay.json). Измерения описывают синтетические изображения и конкретный CPU. Производственная приёмка проверяет оптику, механику, сеть и SDK на выбранном оборудовании.

## Запуск

Python 3.12, CPU. Версия поставки — `submission-v3`.

```bash
git clone https://github.com/gimacorp/ozon-barcode-reader.git
cd ozon-barcode-reader
git checkout submission-v3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m barcode_reader.replay
```

В Windows: `.venv\Scripts\activate`. Для одного декодера достаточно `pip install -r requirements-core.txt`; отчёт использует `requirements-report.txt`, проверки и исполнение Jupyter Notebook — `requirements-test.txt`. Пакет поддерживает `pip install '.[report,test]'`.

Сквозной replay обрабатывает изображения двух коробок с одинаковыми значениями в общем кадре, весь контракт кадров и полос, назначение ROI, финализацию, SQLite Outbox/WCS, потерю ACK и повтор доставки. Ожидается два результата `read`; вариант с пропуском полосы проверяется тестом и даёт `incomplete_views`. Актуальные число тестов, время и версия: [verification.json](results/verification.json).

```bash
python -m barcode_reader decode results/nominal_frame.png --formats Code128
python -m barcode_reader calculate
```

Декодер возвращает пространственные экземпляры с форматом, исходными байтами, текстом и координатами. Объединение по `(формат, байты)` выполняется внутри назначенной коробки. `--formats Code128,DataMatrix,QRCode` расширяет символики; `--enhanced` включает CLAHE и ×2. CLI ограничивает отдельный процесс параметром `--timeout` (по умолчанию 5 с).

## Полное воспроизведение

```bash
python scripts/reproduce.py
```

Последовательный запуск обновляет расчёты, номинальный и стрессовый эксперименты, три нагрузочных прогона, изображения ошибок, PDF и исполненный Jupyter Notebook. На измерительном компьютере следует выделить несколько минут; длительность зависит от CPU и фоновой нагрузки. Все ошибки и просрочки сохраняются.

Каждый эксперимент записывает фактические CPU, ОС, Python, пакеты, Git SHA, признак изменений, хеш исходников и полный конфиг. PDF и README получают измеренные числа из JSON. [Manifest PDF](results/report_manifest.json) фиксирует хеши входов; сборка проверяет совпадение конфигурации. [Описание проверок](docs/validation.md).

Для отдельного запуска:

```bash
python scripts/load_replay.py --boxes 12 --runs 3
python scripts/build_report.py
python scripts/verify_submission.py
```

CI проверяет код, сквозной сценарий, сборку PDF и исполнение Jupyter Notebook. Полный эксперимент доступен отдельным ручным workflow.

## Проектные параметры

| Параметр | Значение |
|---|---|
| Лента / скорость / интервал | 650 мм / 1 м/с / 2 с |
| Коробка | 600 × 400 × 400 мм |
| Модуль / этикетка | X ≥ 0,33 мм / до 78 × 25 мм |
| Значения | До 24 на коробку, четыре этикетки на грань |
| Линейные камеры | 4 × Basler raL8192-80km, 12 кГц, F/8 |
| Торцы | 2 × hr65MXGE, 9344 × 7000, 16 Гц, F/11 |
| Срок после последней экспозиции и резервов | 635 мс |

[Общий конфиг](configs/conveyor.json) управляет расчётами, расписанием, полосами и физической моделью. [Ведомость](docs/bom.json) содержит оптику, питание, адаптеры, триггеры и кабели.

![Номинальный кадр и фрагменты](docs/figures/nominal_reading.png)

## Google Colab

[Открыть Jupyter Notebook](https://colab.research.google.com/github/gimacorp/ozon-barcode-reader/blob/submission-v3/notebooks/demo_ru.ipynb). Выбрать CPU и выполнить ячейки по порядку. Сохранённые выходы ячеек доступны на GitHub: чтение, расчёты, короткий стресс-набор, сквозной обмен и тесты.

## Границы реализации

Прототип реализует декодирование, геометрию назначения, контракт происхождения/полноты захвата, сессии, ограниченную EDF-очередь, долговечные журналы и очистку состояния. `capture_complete` проверяет обязательные данные; `complete_set_verified: false` сохраняет неизвестность физического числа наклеек.

Аппаратная интеграция включает калибровку, SDK камер, DMA общей памяти, watchdog постоянного пула, HTTP-сервис и handshake WCS–ПЛК. Доступные реальные иллюстрации задания проверены; [протокол фотосерии](docs/photo_protocol.md) описывает дополнительную натурную проверку.

Начинайте приёмку с минимального X на торцах при F/11, граничной подачи и кромок нижнего обзора; затем проверяйте нагрузку и доставку на выбранном IPC.
