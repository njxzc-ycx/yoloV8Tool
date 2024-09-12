import os
import sys
import cv2
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QLabel, QMessageBox, QTextEdit
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
from ultralytics import YOLO
import torch  # 新增导入torch
import numpy as np

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ui_file = resource_path("UI/validation.ui")

# 主界面UI配置文件
validationUi, validationBase = uic.loadUiType(ui_file)

class ValidationWidget(QWidget, validationUi):
    def __init__(self):
        super(ValidationWidget, self).__init__()
        self.setupUi(self)

        # 确保左侧和右侧的控件在splitter中正确显示
        self.splitter.setStretchFactor(0, 1)  # 左侧的伸缩因子
        self.splitter.setStretchFactor(1, 0)  # 右侧的伸缩因子

        # 设置图像显示的初始状态
        self.imageDisplayLabel.setText("在此处显示选定的图像")
        self.imageDisplayLabel.setAlignment(Qt.AlignCenter)

        # 绑定按钮点击事件
        self.btn_select_weights.clicked.connect(self.select_weights_file)
        self.btn_select_image.clicked.connect(self.select_image_file)
        self.btn_validate_image.clicked.connect(self.validate_image)

        # 绑定滑块事件
        self.slider_confidence_threshold.valueChanged.connect(self.update_confidence_label)

        self.selected_image_path = None  # 初始化图像路径
        self.selected_model_path = None  # 初始化模型路径

    def select_weights_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "选择 Weights 文件", "",
                                                   "Weights Files (*.weights *.pt);;All Files (*)", options=options)
        if file_name:
            # 提取文件名（不带路径）
            weight_file_name = os.path.basename(file_name)
            # 显示文件名在 pt模型 标签旁边
            self.label_weights.setText(f"pt模型: {weight_file_name}")
            self.selected_model_path = file_name  # 保存选择的模型路径
            QMessageBox.information(self, "提示", f"选择的 Weights 文件: {file_name}")

    def select_image_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "选择图像文件", "",
                                                   "Image Files (*.png *.jpg *.jpeg);;All Files (*)", options=options)
        if file_name:
            # 保存选择的图像路径
            self.selected_image_path = file_name
            # 显示图像
            pixmap = QPixmap(file_name)
            # 使用保持比例和平滑变换的缩放方式
            scaled_pixmap = pixmap.scaled(self.imageDisplayLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.imageDisplayLabel.setPixmap(scaled_pixmap)

    def validate_image(self):
        if not self.selected_model_path:
            QMessageBox.warning(self, "警告", "请先选择模型文件！")
            return

        if not self.selected_image_path:
            QMessageBox.warning(self, "警告", "请先选择图像文件！")
            return


        if torch.cuda.is_available():
            device = 'cuda'
        else:
            device = 'cpu'

        model = YOLO(self.selected_model_path).to(device)

        image = cv2.imread(self.selected_image_path)

        results = model(image)

        confidence_threshold = self.slider_confidence_threshold.value() / 100.0

        result_text = ""

        detection_number = 1
        for result in results:
            boxes = result.boxes
            for box in boxes:

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = box.conf[0]
                cls = int(box.cls[0])


                if conf < confidence_threshold:
                    continue

                label = f"{model.names[cls]} {conf:.2f}"


                result_text += f"编号 {detection_number}: 类别: {model.names[cls]}, 坐标: ({x1}, {y1}), ({x2}, {y2}), 置信度: {conf:.2f}\n"


                cv2.rectangle(image, (x1, y1), (x2, y2), (139, 0, 0), 5)
                cv2.putText(image, f"{detection_number}: {label}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (139, 0, 0), 4)  # 字体大小为2.0，粗细为4

                detection_number += 1


        if not result_text:
            result_text = "没有检测结果超过设定的置信度阈值。"


        self.textEdit_results.setPlainText(result_text)

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


        height, width, channel = image.shape
        bytes_per_line = 3 * width
        q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(q_image)
        scaled_pixmap = pixmap.scaled(self.imageDisplayLabel.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.imageDisplayLabel.setPixmap(scaled_pixmap)

        QMessageBox.information(self, "提示", "识别完成！")

    def update_confidence_label(self):
        current_value = self.slider_confidence_threshold.value() / 100.0
        self.label_threshold_value.setText(f"{current_value:.2f}")
