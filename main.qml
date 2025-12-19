import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: mainWindow
    width: 1200
    height: 700
    title: "Optris Thermal Camera Viewer - QML"
    visible: true

    Rectangle {
        id: mainContainer
        anchors.fill: parent
        color: "#f0f0f0"

        RowLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 10

            // Левая панель - изображение с камеры (70% ширины)
            Rectangle {
                id: imagePanel
                Layout.fillHeight: true
                Layout.preferredWidth: parent.width * 0.7
                color: "#2c3e50"
                border.color: "#34495e"
                border.width: 2
                radius: 5

                Item {
                    anchors.fill: parent
                    anchors.margins: 5

                    Image {
                        id: cameraImage
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectFit
                        cache: false
                        source: "image://thermal/live?" + thermalController.frameCounter
                    }
                }
            }

            // Правая панель - элементы управления (30% ширины)
            ScrollView {
                id: controlPanel
                Layout.fillHeight: true
                Layout.preferredWidth: parent.width * 0.3
                contentWidth: availableWidth

                ColumnLayout {
                    width: controlPanel.availableWidth
                    spacing: 15

                    // Группа управления камерой
                    GroupBox {
                        id: cameraControlGroup
                        title: "Управление камерой"
                        Layout.fillWidth: true

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            Label {
                                text: "Модель: " + thermalController.cameraModel
                                font.bold: true
                            }

                            Label { text: "Формат видеопотока:" }
                            ComboBox {
                                id: videoFormatCombo
                                Layout.fillWidth: true
                                model: thermalController.videoFormats

                                // избегаем binding loop: инициализируем один раз
                                Component.onCompleted: currentIndex = thermalController.currentVideoFormat
                                onCurrentIndexChanged: thermalController.currentVideoFormat = currentIndex
                            }

                            CheckBox {
                                id: autoCalibCheckbox
                                text: "Разрешить автоматическую калибровку"

                                Component.onCompleted: checked = thermalController.autoCalibration
                                onCheckedChanged: thermalController.autoCalibration = checked
                            }

                            Button {
                                text: "Ручная калибровка"
                                Layout.fillWidth: true
                                onClicked: thermalController.trigger_calibration()
                            }

                            Label { text: "Цветовая палитра:" }
                            ComboBox {
                                id: paletteCombo
                                Layout.fillWidth: true
                                model: thermalController.colorPalettes

                                Component.onCompleted: currentIndex = thermalController.currentPalette
                                onCurrentIndexChanged: thermalController.currentPalette = currentIndex
                            }

                            Label {
                                text: "Состояние флага: " + thermalController.flagState
                            }
                        }
                    }

                    // Группа метаданных
                    GroupBox {
                        id: metadataGroup
                        title: "Метаданные"
                        Layout.fillWidth: true

                        GridLayout {
                            width: parent.width
                            columns: 1
                            rowSpacing: 5

                            Label { text: "Разрешение: " + thermalController.resolution }
                            Label { text: "FPS: " + thermalController.fps }
                            Label { text: "Центральная точка: " + thermalController.centralTemp }
                            Label { text: "Средняя температура: " + thermalController.averageTemp }
                            Label { text: "Температура чипа: " + thermalController.chipTemp }
                            Label { text: "Температура флага: " + thermalController.flagTemp }
                            Label { text: "Температура корпуса: " + thermalController.boxTemp }
                            Label { text: "Счетчик кадров: " + thermalController.frameCounter }
                            Label { text: "Временная метка: " + thermalController.timestamp }
                        }
                    }

                    // Группа сохранения данных
                    GroupBox {
                        id: saveGroup
                        title: "Сохранение данных"
                        Layout.fillWidth: true

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            CheckBox {
                                id: saveMetadataCheck
                                text: "Сохранять метаданные (.txt)"

                                Component.onCompleted: checked = thermalController.saveMetadata
                                onCheckedChanged: thermalController.saveMetadata = checked
                            }

                            CheckBox {
                                id: saveTempDataCheck
                                text: "Сохранять температурные данные (.npy)"

                                Component.onCompleted: checked = thermalController.saveTempData
                                onCheckedChanged: thermalController.saveTempData = checked
                            }

                            CheckBox {
                                id: saveImageCheck
                                text: "Сохранять снимок в текущей палитре (.png)"

                                Component.onCompleted: checked = thermalController.saveImage
                                onCheckedChanged: thermalController.saveImage = checked
                            }

                            Label { text: "Метод сохранения PNG:" }
                            ComboBox {
                                id: pngMethodCombo
                                Layout.fillWidth: true
                                model: ["Оптимальный (через SDK)", "Высокоточный (через SDK)", "Исходный (через QPixmap)"]

                                Component.onCompleted: currentIndex = thermalController.pngMethod
                                onCurrentIndexChanged: thermalController.pngMethod = currentIndex
                            }

                            Button {
                                text: "Сделать снимок"
                                Layout.fillWidth: true
                                onClicked: thermalController.save_snapshot()
                            }

                            Button {
                                text: "Тест скорости сохранения"
                                Layout.fillWidth: true
                                onClicked: thermalController.run_speed_test()
                            }
                        }
                    }

                    // Группа записи видео
                    GroupBox {
                        id: videoGroup
                        title: "Запись видео"
                        Layout.fillWidth: true

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            RowLayout {
                                Button {
                                    id: startRecordButton
                                    text: "Начать запись"
                                    Layout.fillWidth: true
                                    enabled: !thermalController.isRecording
                                    onClicked: thermalController.start_recording()
                                }

                                Button {
                                    id: stopRecordButton
                                    text: "Остановить"
                                    Layout.fillWidth: true
                                    enabled: thermalController.isRecording
                                    onClicked: thermalController.stop_recording()
                                }
                            }

                            Label {
                                text: "Время записи: " + thermalController.recordingTime
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                                font.bold: true
                            }
                        }
                    }
                }
            }
        }
    }
}
