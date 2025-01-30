import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QWidget, QVBoxLayout, QPushButton,
    QSpinBox, QHBoxLayout, QListWidget, QMessageBox, QLineEdit, QInputDialog,
    QStackedLayout, QGridLayout
)
from PyQt6.QtGui import QFont, QPixmap, QGuiApplication
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtCore import QUrl


class DisplayWindow(QWidget):
    """Secondary screen that shows the clock or countdown with a custom background."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Display Window")
        self.setStyleSheet("background-color: black;")  # Ensure window background is black
        
        # Background (Image or Video)
        self.background_label = QLabel(self)
        self.background_label.setScaledContents(True)  # Allow background to stretch

        # Video Player for Backgrounds
        self.video_widget = QVideoWidget(self)
        self.video_player = QMediaPlayer()
        self.video_player.setVideoOutput(self.video_widget)
        self.video_player.setLoops(QMediaPlayer.Loops.Infinite)  # Loop video

        # Layout for background elements
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.background_label)
        self.layout.addWidget(self.video_widget)
        self.setLayout(self.layout)

        # Timer Label (placed outside the layout to be on top)
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        label_width = int(screen_geometry.width() * 0.8)
        label_height = int(screen_geometry.height() * (1/3))
        self.label = QLabel("00:00:00", self)
        self.label.setFont(QFont("Arial", label_width // 5, QFont.Weight.Bold))  # Adjust font size dynamically
        self.label.setStyleSheet("color: white; background: transparent;")  # Transparent background
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedSize(label_width, label_height)
        # Scale appropriately

        self.load_background()   # Load the last used background

    def update_display(self, text, remaining_time=None, total_time=None, is_countdown=False):
        """Update the displayed text and reset color when countdown ends."""
        self.label.setText(text)

        # Reset color to white when not in countdown mode
        if not is_countdown or total_time is None or remaining_time is None or total_time == 0:
            self.label.setStyleSheet("color: white; background: transparent;")
        else:
            # Change text color only if it's a countdown and time is low
            if remaining_time / total_time <= 0.2:
                self.label.setStyleSheet("color: red; background: transparent;")
            else:
                self.label.setStyleSheet("color: white; background: transparent;")

    def set_background(self, file_path=None):
        """Set background image, video, or reset to dark mode."""
        if file_path is None:  # Reset to default dark background
            self.background_label.hide()
            self.video_widget.hide()
            self.setStyleSheet("background-color: black;")
        elif file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
            self.video_widget.hide()
            self.background_label.setPixmap(QPixmap(file_path))
            self.background_label.show()
        elif file_path.lower().endswith((".mp4", ".wmv", ".mov")):
            self.background_label.hide()
            self.video_widget.show()
            self.video_player.setSource(QUrl.fromLocalFile(file_path))
            self.video_player.play()

        with open("background.json", "w") as f:
            json.dump({"background": file_path}, f)  # Save selection

    def load_background(self):
        """Load the saved background if available."""
        try:
            with open("background.json", "r") as f:
                data = json.load(f)
                self.set_background(data.get("background", ""))
        except FileNotFoundError:
            pass

    def resizeEvent(self, event):
        """Ensure elements resize properly when the window is resized."""
        super().resizeEvent(event)

        # Ensure background fills the screen
        self.background_label.setGeometry(0, 0, self.width(), self.height())
        self.video_widget.setGeometry(0, 0, self.width(), self.height())

        # Reposition and scale the timer label
        self.label.setFixedSize(self.width() // 2, self.height() // 5)  # Adjust size
        self.label.move((self.width() - self.label.width()) // 2, (self.height() - self.label.height()) // 2)  # Center it


class ControlWindow(QMainWindow):
    """Primary screen (Operator Window) for managing clock, countdown, and scheduler."""
    def __init__(self, app):
        super().__init__()
        self.setWindowTitle("Control Panel")
        self.setGeometry(100, 100, 600, 500)

        # Detect screens
        screen_count = app.screens()
        self.second_screen = screen_count[1] if len(screen_count) > 1 else None

        # Create the display window
        self.display_window = DisplayWindow()
        if self.second_screen:
            self.display_window.move(self.second_screen.geometry().x(), self.second_screen.geometry().y())
            self.display_window.showFullScreen()

        # UI Components
        self.init_ui()

        # Timers
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display_time)
        self.timer.start(1000)  # Update every second

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)

        self.countdown_remaining = QTime(0, 0, 0)
        self.showing_countdown = False
        self.paused = False
        self.scheduler_running = False

        # Scheduler
        self.scheduler_list = []
        self.current_scheduler_index = 0
        self.loop_scheduler = True  # Auto-loop enabled

    def init_ui(self):
        """Create UI elements for countdown settings and scheduler."""
        layout = QVBoxLayout()

        # Countdown Input (Minutes, Seconds, Label)
        time_layout = QHBoxLayout()
        self.minutes_input = QSpinBox()
        self.minutes_input.setRange(0, 59)
        self.minutes_input.setPrefix("Min: ")

        self.seconds_input = QSpinBox()
        self.seconds_input.setRange(0, 59)
        self.seconds_input.setPrefix("Sec: ")

        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Enter label (optional)")

        time_layout.addWidget(self.minutes_input)
        time_layout.addWidget(self.seconds_input)
        time_layout.addWidget(self.label_input)

        # Buttons: Start, Pause, Reset
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Countdown")
        self.start_btn.clicked.connect(self.start_countdown)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_countdown)
        self.pause_btn.setEnabled(False)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_countdown)
        self.reset_btn.setEnabled(False)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.reset_btn)

        # Scheduler Section
        scheduler_layout = QGridLayout()
        self.scheduler_list_widget = QListWidget()
        self.add_to_scheduler_btn = QPushButton("Add to Scheduler")
        self.add_to_scheduler_btn.clicked.connect(self.add_to_scheduler)

        self.start_scheduler_btn = QPushButton("Start Scheduler")
        self.start_scheduler_btn.clicked.connect(self.start_scheduler)
        self.start_scheduler_btn.setEnabled(False)

        self.stop_scheduler_btn = QPushButton("Stop Scheduler")
        self.stop_scheduler_btn.clicked.connect(self.stop_scheduler)
        self.stop_scheduler_btn.setEnabled(False)

        # Save/Load Buttons
        self.save_scheduler_btn = QPushButton("Save Schedule")
        self.save_scheduler_btn.clicked.connect(self.save_scheduler)

        self.load_scheduler_btn = QPushButton("Load Schedule")
        self.load_scheduler_btn.clicked.connect(self.load_scheduler)
        
        # Edit/Delete Buttons
        self.edit_scheduler_btn = QPushButton("Edit Schedule")
        self.edit_scheduler_btn.clicked.connect(self.edit_selected_schedule)
        
        self.delete_timer_btn = QPushButton("Delete Timer")
        self.delete_timer_btn.clicked.connect(self.delete_selected_timer)
        
        self.delete_schedule_btn = QPushButton("Delete Schedule")
        self.delete_schedule_btn.clicked.connect(self.delete_schedule)
        
        # Background Selection Button
        self.set_background_btn = QPushButton("Set Background")
        self.set_background_btn.clicked.connect(self.select_background)
        self.reset_bg_button = QPushButton("Reset Background")
        self.reset_bg_button.clicked.connect(lambda: self.set_background(None))
        
        #Scheduler Layout
        scheduler_layout.addWidget(self.add_to_scheduler_btn, 0, 0)
        scheduler_layout.addWidget(self.start_scheduler_btn, 0, 1)
        scheduler_layout.addWidget(self.stop_scheduler_btn, 0, 2)
        scheduler_layout.addWidget(self.save_scheduler_btn, 1, 0)
        scheduler_layout.addWidget(self.load_scheduler_btn, 1, 1)
        scheduler_layout.addWidget(self.edit_scheduler_btn, 1, 2)
        scheduler_layout.addWidget(self.delete_timer_btn, 2, 0)
        scheduler_layout.addWidget(self.delete_schedule_btn, 2, 1)
        
        #Background Layout
        background_layout = QGridLayout()
        background_layout.addWidget(self.set_background_btn, 0, 0)
        background_layout.addWidget(self.reset_bg_button, 0, 1)
        
        #Control buttons layout
        control_layout = QGridLayout()
        control_layout.addLayout(scheduler_layout, 0, 0)
        control_layout.addLayout(background_layout, 0, 1)
    
        # Add widgets to layout
        layout.addLayout(time_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.scheduler_list_widget)
        layout.addLayout(control_layout)
        

        # Set main widget
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_display_time(self):
        """Update the time on the secondary display only if no countdown is running."""
        if not self.showing_countdown and not self.scheduler_running:
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S")
            self.display_window.update_display(current_time, is_countdown=False)

    def start_countdown(self):
        """Start the countdown."""
        if self.paused:
            self.paused = False
            self.countdown_timer.start(1000)
            return

        minutes = self.minutes_input.value()
        seconds = self.seconds_input.value()
        if minutes == 0 and seconds == 0:
            return  # Ignore if no duration is set

        self.countdown_remaining = QTime(0, minutes, seconds)
        self.showing_countdown = True
        self.countdown_timer.start(1000)  # Update every second
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.update_countdown()

    def pause_countdown(self):
        """Pause the countdown timer."""
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self.paused = True
            self.pause_btn.setText("Resume")
        else:
            self.countdown_timer.start(1000)
            self.paused = False
            self.pause_btn.setText("Pause")

    def reset_countdown(self):
        """Reset the countdown timer and stop scheduler if running."""
        self.countdown_timer.stop()
        self.scheduler_running = False
        self.showing_countdown = False
        self.display_window.update_display("00:00:00")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.stop_scheduler_btn.setEnabled(False)
        self.pause_btn.setText("Pause")

    def add_to_scheduler(self):
        """Add the current countdown settings to the scheduler list."""
        minutes = self.minutes_input.value()
        seconds = self.seconds_input.value()
        label = self.label_input.text().strip()
        time_str = f"{label if label else 'Timer'} - {minutes:02d}:{seconds:02d}"

        if minutes == 0 and seconds == 0:
            return

        self.scheduler_list.append({"time": QTime(0, minutes, seconds), "label": label})
        self.scheduler_list_widget.addItem(time_str)
        self.start_scheduler_btn.setEnabled(True)

    def start_scheduler(self):
        """Start executing the scheduler list."""
        if not self.scheduler_list:
            return

        self.scheduler_running = True
        self.current_scheduler_index = 0
        self.stop_scheduler_btn.setEnabled(True)
        self.load_next_scheduler_countdown()

    def stop_scheduler(self):
        """Stop the scheduler and reset to normal display."""
        self.scheduler_running = False
        self.showing_countdown = False  # Ensure normal time mode
        self.display_window.update_display(QTime.currentTime().toString("hh:mm:ss"))
        self.stop_scheduler_btn.setEnabled(False)
        self.countdown_timer.stop()

    def save_scheduler(self):
        """Save the scheduler list to a named JSON file."""
        if not self.scheduler_list:
            QMessageBox.warning(self, "Error", "No timers in the scheduler to save.")
            return

        # Ensure 'schedules' folder exists
        if not os.path.exists("schedules"):
            os.makedirs("schedules")

        # Ask for a schedule name
        name, ok = QInputDialog.getText(self, "Save Schedule", "Enter a schedule name:")

        if ok and name.strip():
            filename = f"schedules/{name.strip()}.json"
            save_data = [
                {"time": item["time"].toString("mm:ss"), "label": item["label"]}
                for item in self.scheduler_list
            ]

            with open(filename, "w") as f:
                json.dump(save_data, f)

            QMessageBox.information(self, "Success", f"Schedule '{name}' saved successfully!")
            
    def update_countdown(self):
        """Update the countdown display and handle time decrement."""
        if self.countdown_remaining == QTime(0, 0, 0):
            self.countdown_timer.stop()
            self.showing_countdown = False

            if self.scheduler_running and self.current_scheduler_index < len(self.scheduler_list) - 1:
                self.current_scheduler_index += 1
                self.load_next_scheduler_countdown()
            else:
                self.display_window.update_display(QTime.currentTime().toString("hh:mm:ss"), 0, 1)
                self.scheduler_running = False  # Stop scheduler if last item

            return

        self.countdown_remaining = self.countdown_remaining.addSecs(-1)
        total_seconds = self.minutes_input.value() * 60 + self.seconds_input.value()
        remaining_seconds = self.countdown_remaining.minute() * 60 + self.countdown_remaining.second()

        self.display_window.update_display(
            self.countdown_remaining.toString("mm:ss"), 
            remaining_seconds, 
            total_seconds,
            is_countdown=True
        )

    def load_scheduler(self):
        """Load a selected schedule from the saved schedules."""
        # Get all saved schedule files
        if not os.path.exists("schedules"):
            os.makedirs("schedules")

        schedule_files = [f for f in os.listdir("schedules") if f.endswith(".json")]

        if not schedule_files:
            QMessageBox.warning(self, "No Schedules", "No saved schedules found.")
            return

        # Ask user to select a schedule
        schedule_name, ok = QInputDialog.getItem(self, "Load Schedule", 
                                                "Select a schedule to load:", 
                                                schedule_files, 0, False)

        if ok and schedule_name:
            try:
                with open(f"schedules/{schedule_name}", "r") as f:
                    load_data = json.load(f)
                    self.scheduler_list = [
                        {"time": QTime.fromString(item["time"], "mm:ss"), "label": item["label"]}
                        for item in load_data
                    ]
                    self.scheduler_list_widget.clear()
                    for item in self.scheduler_list:
                        self.scheduler_list_widget.addItem(f"{item['label']} - {item['time'].toString('mm:ss')}")

                QMessageBox.information(self, "Success", f"Schedule '{schedule_name}' loaded successfully!")
                self.start_scheduler_btn.setEnabled(True)  # Enable start button after loading
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load schedule: {str(e)}")
            
    def load_next_scheduler_countdown(self):
        """Load and start the next countdown in the scheduler."""
        if not self.scheduler_list or self.current_scheduler_index >= len(self.scheduler_list):
            self.scheduler_running = False
            self.showing_countdown = False
            self.display_window.update_display(QTime.currentTime().toString("hh:mm:ss"))  # Show normal time
            return

        # Get the next countdown settings
        next_timer = self.scheduler_list[self.current_scheduler_index]
        self.countdown_remaining = next_timer["time"]
        self.showing_countdown = True
        self.display_window.update_display(self.countdown_remaining.toString("mm:ss"))
        self.countdown_timer.start(1000)
        
    def edit_selected_schedule(self):
        """Allow user to edit a selected schedule entry."""
        selected_item = self.scheduler_list_widget.currentRow()
        if selected_item < 0:
            QMessageBox.warning(self, "Error", "No schedule item selected.")
            return

        item = self.scheduler_list[selected_item]
        new_label, ok = QInputDialog.getText(self, "Edit Label", "Modify label:", text=item["label"])
        if not ok:
            return

        minutes, ok1 = QInputDialog.getInt(self, "Edit Time", "Minutes:", item["time"].minute(), 0, 59)
        seconds, ok2 = QInputDialog.getInt(self, "Edit Time", "Seconds:", item["time"].second(), 0, 59)
        if not (ok1 and ok2):
            return

        self.scheduler_list[selected_item] = {"time": QTime(0, minutes, seconds), "label": new_label}
        self.scheduler_list_widget.item(selected_item).setText(f"{new_label} - {minutes:02}:{seconds:02}")

    def delete_selected_timer(self):
        """Delete a selected schedule entry."""
        selected_item = self.scheduler_list_widget.currentRow()
        if selected_item < 0:
            QMessageBox.warning(self, "Error", "No schedule item selected.")
            return

        reply = QMessageBox.question(self, "Delete", "Are you sure you want to delete this schedule item?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.scheduler_list[selected_item]
            self.scheduler_list_widget.takeItem(selected_item)

    def delete_schedule(self):
        """Allow the user to select and delete a specific saved schedule."""
        if not os.path.exists("schedules"):
            os.makedirs("schedules")

        schedule_files = [f for f in os.listdir("schedules") if f.endswith(".json")]

        if not schedule_files:
            QMessageBox.warning(self, "No Schedules", "No saved schedules found.")
            return

        schedule_name, ok = QInputDialog.getItem(self, "Delete Schedule", 
                                                "Select a schedule to delete:", 
                                                schedule_files, 0, False)

        if ok and schedule_name:
            os.remove(f"schedules/{schedule_name}")
            QMessageBox.information(self, "Success", f"'{schedule_name}' deleted successfully.")
    
    def select_background(self):
        """Allow user to select a background (image or video)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Background", "", "Images (*.png *.jpg *.jpeg *.bmp);;Videos (*.mp4 *.wmv *.mov)"
        )
        if file_path:
            self.display_window.set_background(file_path)
    
    def closeEvent(self, event):
        """Ensure the app fully closes when the control window is closed."""
        self.display_window.close()  # Close the display window
        QApplication.quit()  # Quit the entire application
        event.accept()    
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    control_window = ControlWindow(app)
    control_window.show()
    sys.exit(app.exec())