# optris-camera-debug

![Application](https://img.shields.io/badge/Application-NDT-green)
![Python](https://img.shields.io/badge/Python-3.10-green)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green)
![Windows](https://custom-icon-badges.demolab.com/badge/Windows-0078D6?logo=windows11&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active%20development-orange)
![License](https://img.shields.io/badge/License-GPLv3-blue)

Инструмент для отладки и работы с тепловизионными камерами Optris через библиотеку libirimager.dll. Приложение предоставляет графический интерфейс для вывода изображения с тепловизора и управления настройками.

## Основные возможности

* Вывод изображения с тепловизора в реальном времени с различными цветовыми палитрами
* Поддержка различных моделей камер Optris через парсинг файла Formats.def
* Управление тепловизором: автоматическая и ручная калибровка, выбор формата (разрешения и FPS)
* Определение температуры в центре карты
* Расчёт средней температуры кадра
* Мониторинг метаданных: состояние флага, температуры чипа и корпуса
* Сохранение данных: метаданные, температурные данные (NumPy), изображения (PNG)
* Запись видео в формате AVI
* Тестирование производительности различных методов сохранения

## Демонстрация работы

Приложение предоставляет интуитивно понятный интерфейс с изображением в левой части и панелью управления в правой части:

![Снимок основного окна](screenshots/main_window.png)

## Структура проекта

optris-camera-debug/  
├── 📁 screenshots/ ---------------- Скриншоты для документации  
├── 📄 .gitignore ------------------ Исключения git  
├── 📄 Formats.def ----------------- Файл определений форматов камер  
├── 📄 generic.xml ----------------- XML-конфиг: настройки подключения и параметров камеры  
├── 📄 libirimager.dll ------------- DLL библиотека Optris  
├── 📄 LICENSE --------------------- Лицензия проекта  
├── 📄 optris_camera_debug_tool.py - Основное приложение  
└── 📄 README.md ------------------- Документация (этот файл)  

## Быстрый старт

### Предварительные требования

* Windows 10/11
* Python 3.10
* Библиотека libirimager.dll (включена в проект)
* Драйвера, устанавливаемые вместе с [Optris Pix Connect](https://optris.com/us/software/pixconnect/) (тестировалось только с PIX Connect 3.24.3127.0)
<!-- TODO: Узнать что именно там устанавливается вместе с приложением, без чего проект не запускается -->

### Установка зависимостей

```bash
pip install numpy opencv-python PySide6
```

### Запуск приложения

```bash
python optris_camera_debug_tool.py
```
