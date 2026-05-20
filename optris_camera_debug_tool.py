import sys
import os
import numpy as np
import ctypes as ct
import time
from datetime import datetime
import cv2

from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QObject, Signal, Property, QTimer, QUrl, Slot
from PySide6.QtGui import QImage, QIcon
from PySide6.QtQuick import QQuickImageProvider


# --- Структура метаданных ---
class EvoIRFrameMetadata(ct.Structure):
    _fields_ = [
        ("counter", ct.c_uint),
        ("counterHW", ct.c_uint),
        ("timestamp", ct.c_longlong),
        ("timestampMedia", ct.c_longlong),
        ("flagState", ct.c_int),
        ("tempChip", ct.c_float),
        ("tempFlag", ct.c_float),
        ("tempBox", ct.c_float),
    ]


# --- Менеджер камеры ---
class CameraManager:
    def __init__(self):
        self.libir = None

    def init_library(self):
        try:
            self.libir = ct.CDLL('./libirimager.dll')

            self.libir.evo_irimager_usb_init.argtypes = [ct.c_char_p, ct.c_char_p, ct.c_char_p]
            self.libir.evo_irimager_usb_init.restype = ct.c_int

            self.libir.evo_irimager_get_thermal_image_size.argtypes = [
                ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)
            ]
            self.libir.evo_irimager_get_palette_image_size.argtypes = [
                ct.POINTER(ct.c_int), ct.POINTER(ct.c_int)
            ]

            self.libir.evo_irimager_get_thermal_palette_image_metadata.argtypes = [
                ct.c_int, ct.c_int, ct.POINTER(ct.c_ushort),
                ct.c_int, ct.c_int, ct.POINTER(ct.c_ubyte),
                ct.POINTER(EvoIRFrameMetadata)
            ]
            self.libir.evo_irimager_get_thermal_palette_image_metadata.restype = ct.c_int

            self.libir.evo_irimager_set_palette.argtypes = [ct.c_int]
            self.libir.evo_irimager_set_shutter_mode.argtypes = [ct.c_int]
            self.libir.evo_irimager_trigger_shutter_flag.argtypes = []
            self.libir.evo_irimager_terminate.argtypes = []

            return True
        except Exception as e:
            print(f"Ошибка загрузки DLL: {e}")
            return False

    def init_camera(self, xml_path='generic.xml'):
        if not self.libir:
            if not self.init_library():
                return False
        try:
            ret = self.libir.evo_irimager_usb_init(xml_path.encode(), b'', b'')
            if ret != 0:
                print(f"Ошибка инициализации камеры: {ret}")
                return False

            w, h = ct.c_int(), ct.c_int()
            self.libir.evo_irimager_get_thermal_image_size(ct.byref(w), ct.byref(h))

            pw, ph = ct.c_int(), ct.c_int()
            self.libir.evo_irimager_get_palette_image_size(ct.byref(pw), ct.byref(ph))

            return {
                'thermal_width': w.value,
                'thermal_height': h.value,
                'palette_width': pw.value,
                'palette_height': ph.value
            }
        except Exception as e:
            print(f"Ошибка init_camera: {e}")
            return False

    def deinit_camera(self):
        if self.libir:
            self.libir.evo_irimager_terminate()


# --- ImageProvider, отдающий QImage из ОЗУ ---
class ThermalImageProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image)
        self._image = QImage()

    def setImage(self, image: QImage):
        self._image = image

    def requestImage(self, id, size, requestedSize):
        if not self._image.isNull():
            if size is not None:
                size.setWidth(self._image.width())
                size.setHeight(self._image.height())
            return self._image
        return QImage()


# --- Контроллер камеры ---
class ThermalCameraController(QObject):
    dataUpdated = Signal()
    recordingStateChanged = Signal()

    def __init__(self, image_provider: ThermalImageProvider):
        super().__init__()

        # --- свойства ---
        self._cameraModel = "Optris PI 640"
        self._resolution = "0x0"
        self._fps = "0.0"
        self._centralTemp = "-- °C"
        self._averageTemp = "-- °C"
        self._chipTemp = "-- °C"
        self._flagTemp = "-- °C"
        self._boxTemp = "-- °C"
        self._frameCounter = "--"
        self._timestamp = "--"
        self._flagState = "--"
        self._recordingTime = "0 сек"
        self._isRecording = False

        self._saveMetadata = True
        self._saveTempData = True
        self._saveImage = True
        self._pngMethod = 0

        self._videoFormats = ["Format 1", "Format 2", "Format 3"]
        self._currentVideoFormat = 0

        self._colorPalettes = [
            "Alarm Blue", "Pinkblue", "Bone", "Grayblack", "Alarm Green",
            "Iron", "Orange", "Medical", "Rain", "Rainbow", "Alarm Red"
        ]
        self._currentPalette = 5
        self._autoCalibration = True

        # --- провайдер изображений ---
        self.image_provider = image_provider

        # --- менеджер камеры ---
        self.camera_manager = CameraManager()
        self.camera_info = self.camera_manager.init_camera()
        if not self.camera_info:
            print("Ошибка инициализации камеры")
            return

        self.thermal_width = self.camera_info['thermal_width']
        self.thermal_height = self.camera_info['thermal_height']
        self.palette_width = self.camera_info['palette_width']
        self.palette_height = self.camera_info['palette_height']
        self._resolution = f"{self.thermal_width}x{self.thermal_height}"

        # --- буферы ---
        self.np_thermal = np.zeros([self.thermal_width * self.thermal_height], dtype=np.uint16)
        self.np_img = np.zeros([self.palette_width * self.palette_height * 3], dtype=np.uint8)
        self.metadata = EvoIRFrameMetadata()

        # --- таймер ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # ~33 FPS

        self.frame_count = 0
        self.last_update_time = time.time()

        # --- запись видео ---
        self.recording = False
        self.record_start_time = 0
        self.record_duration = 0
        self.video_writer = None

    # ============================================================
    #  PROPERTIES (QML)
    # ============================================================

    @Property(str, notify=dataUpdated)
    def cameraModel(self):
        return self._cameraModel

    @Property(str, notify=dataUpdated)
    def resolution(self):
        return self._resolution

    @Property(str, notify=dataUpdated)
    def fps(self):
        return self._fps

    @Property(str, notify=dataUpdated)
    def centralTemp(self):
        return self._centralTemp

    @Property(str, notify=dataUpdated)
    def averageTemp(self):
        return self._averageTemp

    @Property(str, notify=dataUpdated)
    def chipTemp(self):
        return self._chipTemp

    @Property(str, notify=dataUpdated)
    def flagTemp(self):
        return self._flagTemp

    @Property(str, notify=dataUpdated)
    def boxTemp(self):
        return self._boxTemp

    @Property(str, notify=dataUpdated)
    def frameCounter(self):
        return self._frameCounter

    @Property(str, notify=dataUpdated)
    def timestamp(self):
        return self._timestamp

    @Property(str, notify=dataUpdated)
    def flagState(self):
        return self._flagState

    @Property(bool, notify=dataUpdated)
    def saveMetadata(self):
        return self._saveMetadata

    @saveMetadata.setter
    def saveMetadata(self, value):
        self._saveMetadata = value
        self.dataUpdated.emit()

    @Property(bool, notify=dataUpdated)
    def saveTempData(self):
        return self._saveTempData

    @saveTempData.setter
    def saveTempData(self, value):
        self._saveTempData = value
        self.dataUpdated.emit()

    @Property(bool, notify=dataUpdated)
    def saveImage(self):
        return self._saveImage

    @saveImage.setter
    def saveImage(self, value):
        self._saveImage = value
        self.dataUpdated.emit()

    @Property(int, notify=dataUpdated)
    def pngMethod(self):
        return self._pngMethod

    @pngMethod.setter
    def pngMethod(self, value):
        self._pngMethod = value
        self.dataUpdated.emit()

    @Property('QVariantList', constant=True)
    def videoFormats(self):
        return self._videoFormats

    @Property(int, notify=dataUpdated)
    def currentVideoFormat(self):
        return self._currentVideoFormat

    @currentVideoFormat.setter
    def currentVideoFormat(self, value):
        self._currentVideoFormat = value
        print("Выбран формат:", self._videoFormats[value])
        self.dataUpdated.emit()

    @Property('QVariantList', constant=True)
    def colorPalettes(self):
        return self._colorPalettes

    @Property(int, notify=dataUpdated)
    def currentPalette(self):
        return self._currentPalette

    @currentPalette.setter
    def currentPalette(self, value):
        if value != self._currentPalette:
            self.set_palette(value)

    @Property(bool, notify=dataUpdated)
    def autoCalibration(self):
        return self._autoCalibration

    @autoCalibration.setter
    def autoCalibration(self, value):
        self.toggle_auto_calib(value)

    @Property(str, notify=recordingStateChanged)
    def recordingTime(self):
        return self._recordingTime

    @Property(bool, notify=recordingStateChanged)
    def isRecording(self):
        return self._isRecording

    # ============================================================
    #  CAMERA FRAME UPDATE
    # ============================================================

    def update_frame(self):
        try:
            ret = self.camera_manager.libir.evo_irimager_get_thermal_palette_image_metadata(
                self.thermal_width, self.thermal_height,
                self.np_thermal.ctypes.data_as(ct.POINTER(ct.c_ushort)),
                self.palette_width, self.palette_height,
                self.np_img.ctypes.data_as(ct.POINTER(ct.c_ubyte)),
                ct.byref(self.metadata)
            )
            if ret != 0:
                print(f"Ошибка получения кадра: {ret}")
                return

            # np_img -> RGB -> QImage
            img_rgb = self.np_img.reshape(
                self.palette_height, self.palette_width, 3
            )[:, :, ::-1].copy()
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

            # кладём кадр в провайдер
            self.image_provider.setImage(qimg)

            # FPS
            self.frame_count += 1
            current_time = time.time()
            elapsed = current_time - self.last_update_time
            if elapsed > 1.0:
                self._fps = f"{self.frame_count / elapsed:.1f}"
                self.frame_count = 0
                self.last_update_time = current_time

            # Температура в центре
            center_index = (self.thermal_height // 2) * self.thermal_width + (self.thermal_width // 2)
            raw_temp = self.np_thermal[center_index]
            temp_c = (raw_temp / 10.0) - 100.0
            self._centralTemp = f"{temp_c:.2f} °C"

            # Средняя температура кадра
            temperatures = (self.np_thermal.astype(np.float32) / 10.0) - 100.0
            avg_temp = np.mean(temperatures)
            self._averageTemp = f"{avg_temp:.2f} °C"

            # Остальные метаданные
            self._chipTemp = f"{self.metadata.tempChip:.2f} °C"
            self._flagTemp = f"{self.metadata.tempFlag:.2f} °C"
            self._boxTemp = f"{self.metadata.tempBox:.2f} °C"
            self._frameCounter = str(self.metadata.counter)
            self._timestamp = str(self.metadata.timestamp)
            self._flagState = str(self.metadata.flagState)

            if self.recording:
                self.update_record_time()

            self.dataUpdated.emit()

            # Запись видео
            if self.recording and self.video_writer is not None:
                self.video_writer.write(img_rgb)

        except Exception as e:
            print(f"Ошибка в update_frame: {e}")

    # ============================================================
    #  CAMERA CONTROL
    # ============================================================

    @Slot(bool)
    def toggle_auto_calib(self, enabled: bool):
        try:
            mode = 1 if enabled else 0
            ret = self.camera_manager.libir.evo_irimager_set_shutter_mode(mode)
            if ret != 0:
                print("Ошибка установки автофлага:", ret)
            self._autoCalibration = enabled
            self.dataUpdated.emit()
        except Exception as e:
            print("Ошибка toggle_auto_calib:", e)

    @Slot()
    def trigger_calibration(self):
        try:
            ret = self.camera_manager.libir.evo_irimager_trigger_shutter_flag()
            if ret != 0:
                print("Ошибка ручной калибровки:", ret)
        except Exception as e:
            print("Ошибка trigger_calibration:", e)

    def set_palette(self, palette_index: int):
        try:
            palette_id = palette_index + 1
            ret = self.camera_manager.libir.evo_irimager_set_palette(palette_id)
            if ret != 0:
                print("Ошибка установки палитры:", ret)
            else:
                self._currentPalette = palette_index
                self.dataUpdated.emit()
        except Exception as e:
            print("Ошибка set_palette:", e)

    @Slot(int)
    def set_video_format(self, index: int):
        try:
            self.currentVideoFormat = index
        except Exception as e:
            print("Ошибка set_video_format:", e)

    # ============================================================
    #  SAVE SNAPSHOT
    # ============================================================

    @Slot()
    def save_snapshot(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"thermal_{timestamp}"

            if self._saveMetadata:
                meta_filename = f"{base_filename}_metadata.txt"
                with open(meta_filename, 'w', encoding='utf-8') as f:
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Resolution: {self._resolution}\n")
                    f.write(f"Flag state: {self._flagState}\n")
                    f.write(f"Chip temperature: {self._chipTemp}\n")
                    f.write(f"Flag temperature: {self._flagTemp}\n")
                    f.write(f"Box temperature: {self._boxTemp}\n")
                    f.write(f"Central temperature: {self._centralTemp}\n")
                    f.write(f"Average temperature: {self._averageTemp}\n")
                print(f"Сохранены метаданные: {meta_filename}")

            if self._saveTempData:
                temp_filename = f"{base_filename}_data.npy"
                data_2d = self.np_thermal.reshape(self.thermal_height, self.thermal_width)
                np.save(temp_filename, data_2d)
                print(f"Сохранены температурные данные: {temp_filename}")

            if self._saveImage:
                img_filename = f"{base_filename}_image.png"
                img_rgb = self.np_img.reshape(
                    self.palette_height, self.palette_width, 3
                )[:, :, ::-1].copy()
                cv2.imwrite(img_filename, img_rgb)
                print(f"Сохранено изображение: {img_filename}")

        except Exception as e:
            print(f"Ошибка сохранения снимка: {e}")

    @Slot()
    def run_speed_test(self):
        print("Запуск теста скорости...")
        self.save_snapshot()

    # ============================================================
    #  VIDEO RECORDING
    # ============================================================

    @Slot()
    def start_recording(self):
        try:
            if self.recording:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thermal_video_{timestamp}.avi"
            fps = max(1, int(float(self._fps) if self._fps != "0.0" else 9))
            frame_size = (self.palette_width, self.palette_height)
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            self.video_writer = cv2.VideoWriter(filename, fourcc, fps, frame_size)

            if not self.video_writer.isOpened():
                print("Ошибка создания видеофайла")
                self.video_writer = None
                return

            self.recording = True
            self._isRecording = True
            self.record_start_time = time.time()
            self.record_duration = 0
            self._recordingTime = "0 сек"
            self.recordingStateChanged.emit()
            print(f"Начата запись видео: {filename}")

        except Exception as e:
            print(f"Ошибка начала записи: {e}")

    @Slot()
    def stop_recording(self):
        try:
            if not self.recording:
                return

            self.recording = False
            self._isRecording = False

            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
                print(f"Видео сохранено, длительность: {self.record_duration} сек")

            self.recordingStateChanged.emit()

        except Exception as e:
            print(f"Ошибка остановки записи: {e}")

    def update_record_time(self):
        if self.recording:
            self.record_duration = int(time.time() - self.record_start_time)
            self._recordingTime = f"{self.record_duration} сек"
            self.recordingStateChanged.emit()


def main():
    app = QApplication(sys.argv)
    
    # Кроссплатформенный выбор иконки
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, "icons", "app_icon.ico")
    png_path = os.path.join(base_dir, "icons", "app_icon.png")
    
    if sys.platform == "win32" and os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))
    elif os.path.exists(png_path):
        app.setWindowIcon(QIcon(png_path))

    engine = QQmlApplicationEngine()

    # провайдер изображений
    image_provider = ThermalImageProvider()
    engine.addImageProvider("thermal", image_provider)

    # контроллер
    controller = ThermalCameraController(image_provider)
    engine.rootContext().setContextProperty("thermalController", controller)

    qml_file = os.path.join(os.path.dirname(__file__), "main.qml")
    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        sys.exit(-1)

    print("Приложение успешно запущено")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
