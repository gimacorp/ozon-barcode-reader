"""Содержательная часть отчёта; числовые результаты берутся из файлов прогона."""

SOURCES = [
 ("Условие: мастерская Ozon, CV, вариант 2", "https://docs.google.com/document/d/1mkqW0bW2fNh_6hSne3xasKlrhmOOrRw6mmtbPp4pUrU/edit?tab=t.croqf6r91zx2"),
 ("Basler: raL8192-80km", "https://www.baslerweb.com/en-us/shop/ral8192-80km/"),
 ("Allied Vision: hr65MXGE, F004121", "https://www.alliedvision.com/en/products/area-scan-cameras/hr/hr-10gige/view/2005"),
 ("Schneider-Kreuznach: объективы EMERALD и адаптеры V48", "https://schneiderkreuznach.com/en/industrial-optics/lenses/large-format-lenses/emerald"),
 ("SICK: WL12-3P1151, 1041449", "https://cdn.sick.com/media/pdf/0/20/320/dataSheet_WL12-3P1151_1041449_en.pdf"),
 ("SICK: DFS60A-S4PC65536, 1036726", "https://www.sick.com/media/pdf/8/58/958/dataSheet_DFS60A-S4PC65536_1036726_en.pdf"),
 ("Basler: microEnable 5 marathon", "https://docs.baslerweb.com/frame-grabbers/microenable-5-marathon"),
 ("CCS: линейный свет LNSP2-700SW", "https://www.ccs-grp.com/products/model/1888"),
 ("Smart Vision Lights: L300G2", "https://smartvisionlights.com/products/l300g2-linear-light/"),
 ("Advantech: паспорт AIMB-788, редакция 2025", "https://advdownload.advantech.com/productfile/PIS/AIMB-788/file/AIMB-788_DS%28082125%2920250829163609.pdf"),
 ("Advantech: конфигурации на AIMB-788", "https://buy.advantech.com/Configure-System/bymodel-AIMB-788.htm"),
 ("Intel: X550-T2, спецификация", "https://www.intel.com/content/www/us/en/products/sku/88209/intel-ethernet-converged-network-adapter-x550t2/specifications.html"),
 ("Basler: настройка качества изображения", "https://docs.baslerweb.com/optimizing-image-quality"),
 ("GS1: выбор штрихкода, X-размер и свободные зоны", "https://www.gs1.org/standards/barcodes/10-steps-to-barcode-your-product/english"),
 ("ZXing-C++: исходный код и поддерживаемые форматы", "https://github.com/zxing-cpp/zxing-cpp"),
 ("ZXing-C++: интерфейс Python, тег v3.1.1", "https://github.com/zxing-cpp/zxing-cpp/blob/v3.1.1/wrappers/python/zxing.cpp"),
 ("OpenCV: геометрическая калибровка", "https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html"),
 ("python-barcode: документация генератора", "https://python-barcode.readthedocs.io/en/stable/"),
 ("Cognex: пример промышленного чтения нижней грани", "https://www.cognex.com/library/media/press-release-media/press-release-pdfs/cognex-bottom-side-barcode-reading-system.pdf"),
 ("Репозиторий решения: код, тесты, исходные результаты", "https://github.com/gimacorp/ozon-barcode-reader"),
]

SOURCES += [
 ('Basler racer Camera Link: AW001185, v08, 29.04.2019', 'https://assets-ctf.baslerweb.com/dg51pdwahxgw/a2xPgcbOSBjF74h6k0daa/2576f46316e1cab5b1cd2f09f8e5544a/AW00118508000_racer_CL_User_Manual.pdf'),
 ('Schneider EMERALD 1071610: паспорт, 09/2024', 'https://schneiderkreuznach.com/application/files/9217/2648/4634/EMERALD_28_28_V48-LD_1071610_datasheet.pdf'),
 ('Basler: баланс дифракции и аберраций, AW001406', 'https://docs.baslerweb.com/knowledge/why-do-the-basler-lenses-have-an-orange-dot-for-fstop-28-value'),
 ('Basler: адаптер 2000033271, M42×1 FBD16', 'https://www.baslerweb.com/en-us/shop/m42x1-mount-fbd-16-mm-for-boost-racer-basler-beat/'),
 ('Basler: Opto-Coupled Trigger 5, 2200000371', 'https://docs.baslerweb.com/frame-grabbers/opto-coupled-trigger-5'),
 ('MEAN WELL: RSP-750, спецификация 10.01.2025', 'https://www.meanwell.com/Upload/PDF/RSP-750/RSP-750-spec.pdf'),
 ('MEAN WELL: HDR, каталог KNX 2026', 'https://www.meanwell.com/Upload/PDF/KNX_EN_2026.pdf'),
 ('CCS: таблица контроллеров PSB4, 300 Вт/канал', 'https://www.ccs-grp.com/ecsuites/media/download/catalog/C_controlUnit_guide_e.pdf'),
 ('Schneider-Kreuznach: каталог изделий 2025', 'https://schneiderkreuznach.com/application/files/2317/5162/8318/Schneider_Kreuznach_Products_2025.pdf'),
 ('Basler: marathon VCL, AW001656, v29, 25.08.2026', 'https://docs.baslerweb.com/frame-grabbers/marathon-vcl'),
]
