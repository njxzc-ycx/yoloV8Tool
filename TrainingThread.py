import logging
import os
import sys

import torch
from PyQt5.QtCore import QThread, pyqtSignal
from ultralytics import YOLO
from contextlib import redirect_stdout
import io
import glob

class StreamToLogger:
    """
    自定义类，将 stdout 和 stderr 重定向到 PyQt 信号
    """
    def __init__(self, signal):
        self.signal = signal
        self.line_buf = ""

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.signal.emit(line)

    def flush(self):
        pass

class TrainingThread(QThread):
    # 定义信号
    trainingStarted = pyqtSignal()
    trainingFinished = pyqtSignal(str,str)
    trainingError = pyqtSignal(str)
    trainingOutput = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super(TrainingThread, self).__init__(parent)
        self.config = config

    def run(self):
        try:
            self.trainingStarted.emit()

            # 将标准输出和错误重定向到信号
            stdout_logger = StreamToLogger(self.trainingOutput)
            stderr_logger = StreamToLogger(self.trainingOutput)
            sys.stdout = stdout_logger
            sys.stderr = stderr_logger

            # 初始化YOLO模型
            model = YOLO(self.config['weights'])

            if torch.cuda.is_available():
                device = 'cuda'
            else:
                device = 'cpu'

            # 捕获训练输出
            with redirect_stdout(io.StringIO()) as f:
                # 调用YOLO训练函数
                results = model.train(
                    data=self.config['datasets'] + '/dataset.yaml',
                    epochs=int(self.config['epoch']),
                    batch=int(self.config['batch_size']),
                    imgsz=int(self.config['imgsz']),
                    device=device,
                    lr0=float(self.config['learning_rate']),
                    weight_decay=float(self.config['weight_decay']),
                    momentum=float(self.config['momentum']),
                    pretrained=self.config['pretrained'],
                    augment=self.config['augment']
                )

                self.trainingOutput.emit(f.getvalue())

            output_dir = results.save_dir

            weight_files = glob.glob(os.path.join(output_dir, 'weights', '*.pt'))
            if weight_files:
                best_model_path = next((f for f in weight_files if 'best.pt' in f), weight_files[0])
                last_model_path = next((f for f in weight_files if 'last.pt' in f), weight_files[0])
                self.trainingFinished.emit(best_model_path,last_model_path)
            else:
                self.trainingFinished.emit("")

        except Exception as e:
            self.trainingError.emit(str(e))

        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
