# main.py
import logging
from logger import setup_logging
from gui import SimGUI
import tkinter as tk
import sys
import io


if __name__ == "__main__":
    # Start the logging system:
    setup_logging("my_detailed.log")  
    # This sets root logger to DEBUG, so file gets everything, console gets INFO+.

    root = tk.Tk()
    app = SimGUI(root)
    root.mainloop()

    logging.info("Simulation closed.")
