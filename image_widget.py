# -*- coding: utf-8 -*-
import sys
import os
if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
from PyQt5.QtWidgets import *
from PyQt5 import QtCore, QtGui, uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import copy
import xml.etree.cElementTree as et
import os
import cv2
import math
from PIL import Image

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ui_file = resource_path("UI/image_widget.ui")

# ui配置文件
cUi, cBase = uic.loadUiType(ui_file)

# 主界面
class CImageWidget(QWidget, cUi):
    def __init__(self):
        # 设置UI
        QMainWindow.__init__(self)
        cUi.__init__(self)
        self.setupUi(self)

        self.setMouseTracking(True)
        self.setCursor(Qt.UpArrowCursor)

        #image信息
        self.img_path = ''
        self.img_name = ''
        self.img = None

        # 已标注信息
        self.box_list = []

        #待标注信息
        self.current_class = -1
        self.start_label = False
        self.current_box = [0,0,0,0,0]

        #显示信息
        self.det_color = [QColor(255, 0, 0),
                          QColor(0, 255, 0),
                          QColor(0, 255, 255),
                          QColor(255, 0, 255),
                          QColor(0, 255, 255)]
        self.det_width = 2
        self.line_color = QColor(255, 255, 0)
        self.line_width = 1

        #当前鼠标信息
        self.current_x = 0
        self.current_y = 0

    def closeEvent(self, event):
        pass

    def set_info(self, image_path, box_list=None):
        if image_path is None:
            self.img_path = ''
            self.img_name = ''
            self.img = None
            self.box_list = []
            self.start_label = False
            self.current_box = [0, 0, 0, 0, 0]
        else:
            self.img_path = image_path
            self.img_name = os.path.basename(image_path) #.split('.')[0]

            #self.img = QPixmap(self.img_path)
            img_cv = cv2.imread(self.img_path)
            if img_cv is not None:
                height, width, depth = img_cv.shape
                img_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                qimage_temp = QImage(img_cv.data, width, height, width * depth, QImage.Format_RGB888)
                self.img = QPixmap.fromImage(qimage_temp)

            if box_list is not None:
                self.box_list = box_list
            else:
                self.box_list = []
        self.update()

    def set_current_cls(self, cls):
        self.current_box[4] = cls

    def get_info(self):
        # filter the area < 10
        flit_box_list = []
        for box in self.box_list:
            x1 = float(box[0])
            y1 = float(box[1])
            x2 = float(box[2])
            y2 = float(box[3])
            area = (x2-x1) * (y2-y1)
            if area > 10.0:
                flit_box_list.append(box)
        return self.img_name, flit_box_list

    def draw_background(self, painter):
        pen = QPen()
        pen.setColor(QColor(0, 0, 0))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width(), self.height())

    def draw_image(self, painter):
        if self.img is not None:
            #print(self.img.width(), self.img.height())
            painter.drawPixmap(QtCore.QRect(0, 0, self.width(), self.height()), self.img)
            #painter.drawPixmap(QtCore.QRect(0, 0, self.img.width(), self.img.height()), self.img)
            painter.drawText(10,20,str(self.img_name))

    def draw_det_info(self, painter):
        for rect in self.box_list:
            pen = QPen()
            pen.setColor(self.det_color[int(rect[4]) % len(self.det_color)])
            pen.setWidth(self.det_width)
            painter.setPen(pen)
            painter.drawRect(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             (rect[2]-rect[0]) * self.width() / self.img.width(),
                             (rect[3]-rect[1]) * self.height() / self.img.height())
            painter.drawText(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             str(int(rect[4])))
        if self.start_label:
            rect = self.current_box
            pen = QPen()
            pen.setColor(self.det_color[int(rect[4]) % len(self.det_color)])
            pen.setWidth(self.det_width)
            painter.setPen(pen)
            painter.drawRect(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             (rect[2] - rect[0]) * self.width() / self.img.width(),
                             (rect[3] - rect[1]) * self.height() / self.img.height())
            painter.drawText(rect[0] * self.width() / self.img.width(),
                             rect[1] * self.height() / self.img.height(),
                             str(int(rect[4])))

    def draw_line(self, painter):
        pen = QPen()
        pen.setColor(self.line_color)
        pen.setWidth(self.line_width)
        painter.setPen(pen)
        painter.drawLine(QPoint(self.current_x, 0), QPoint(self.current_x,5000))
        painter.drawLine(QPoint(0, self.current_y), QPoint(5000,self.current_y))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        self.draw_background(painter)
        self.draw_image(painter)
        self.draw_det_info(painter)
        self.draw_line(painter)

    def mousePressEvent(self, e):
        # 如果当前没有加载图像，直接返回
        if self.img is None:
            return super().mousePressEvent(e)

        # 左键按下开始标注
        if e.button() == QtCore.Qt.LeftButton:
            # 检查是否选择了标注类别
            if self.current_class == -1:
                QMessageBox.information(self, "提示", "请选择标注类别", QMessageBox.Yes)
                return super().mousePressEvent(e)


            self.start_label = True
            self.current_box[0] = e.pos().x() * self.img.width() / self.width()
            self.current_box[1] = e.pos().y() * self.img.height() / self.height()
            self.current_box[2] = self.current_box[0]
            self.current_box[3] = self.current_box[1]

        # 右键按下用于撤销最近的标注框
        if e.button() == QtCore.Qt.RightButton and len(self.box_list) > 0:
            self.box_list.pop()

        self.update()  # 更新绘制
        return super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.img is None:
            return
        self.current_box[2] = e.pos().x() * self.img.width() / self.width()
        self.current_box[3] = e.pos().y() * self.img.height() / self.height()
        self.current_x = e.pos().x()
        self.current_y = e.pos().y()
        #print(self.current_x, self.current_y, e.button())
        self.update()

    def set_current_class(self, cls):
        """设置当前的标注类别。"""
        print(f"Setting current class to: {cls}")
        self.current_class = cls

    def mouseReleaseEvent(self, e):

        # 如果图像不存在，则返回
        if self.img is None:
            return super().mouseReleaseEvent(e)

        # 计算鼠标释放位置
        x1 = e.pos().x()
        y1 = e.pos().y()

        # 确保位置在窗口边界内
        x1 = max(0, min(x1, self.width()))
        y1 = max(0, min(y1, self.height()))

        # 转换为相对于图像的坐标
        x1 = x1 * self.img.width() / self.width()
        y1 = y1 * self.img.height() / self.height()

        # 如果左键释放，进行标注框的创建和调整
        if e.button() == QtCore.Qt.LeftButton:
            self.start_label = False  # 停止标注
            print(f"Current class for annotation: {self.current_class}")
            self.current_box[4] = self.current_class
            self.current_box[2] = min(x1, self.img.width())
            self.current_box[3] = min(y1, self.img.height())

            # 调整坐标确保左上角和右下角位置正确
            if self.current_box[0] > self.current_box[2]:
                self.current_box[0], self.current_box[2] = self.current_box[2], self.current_box[0]
            if self.current_box[1] > self.current_box[3]:
                self.current_box[1], self.current_box[3] = self.current_box[3], self.current_box[1]

            # 添加到标注框列表中
            if (self.current_box[2] - self.current_box[0]) * (self.current_box[3] - self.current_box[1]) >= 1:
                self.box_list.append(copy.deepcopy(self.current_box))

        self.update()  # 更新绘制
        return super().mouseReleaseEvent(e)

    def leaveEvent(self, e):
        self.current_x = 0
        self.current_y = 0
        self.update()

if __name__ == "__main__":
    cApp = QApplication(sys.argv)
    cImageWidget = CImageWidget()
    cImageWidget.show()
    cImageWidget.set_info('logo.png')
    sys.exit(cApp.exec_())