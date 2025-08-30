import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw
import google.generativeai as genai
import os
import json
import threading
import io
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import calendar
import pytesseract
import cv2
import numpy as np
import logging
import pdfplumber
import random
# ✨ NEW: Imports for Voice Agent
import speech_recognition as sr
from gtts import gTTS
from playsound import playsound

# --- Configuration ---
# 🚨 Replace with your VALID Gemini API Key
API_KEY = 'AIzaSyBcEqG-Wx64WB8V5fW8qHAMLIhHkLth4Q4'

# ✨ NEW: Pluggable LLM Agent Architecture
class BaseAgent:
    """A base class for all pluggable LLM agents."""
    def get_response(self, user_message: str, profile_data: dict) -> str:
        """Processes user text and returns the LLM's response."""
        raise NotImplementedError("Each agent must implement its own get_response method.")

class NutritionCoachAgent(BaseAgent):
    """Domain-specific agent for health and nutrition advice."""
    def get_response(self, user_message: str, profile_data: dict) -> str:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Use profile data to give personalized advice
        profile_summary = f"User profile: Age - {profile_data.get('age', 'N/A')}, Goals - {profile_data.get('goals', 'N/A')}, Allergies - {profile_data.get('allergies', 'N/A')}."
        prompt = f"""
        You are a friendly, encouraging, and knowledgeable AI Health Coach for the NutriScanAI app.
        Based on the user's profile, give a helpful response to their question.
        You CAN suggest safe over-the-counter products, nutrition tips, and wellness advice.
        Keep answers clear, concise (2–5 sentences), and practical.
        ---
        {profile_summary}
        ---
        User's question: "{user_message}"
        """
        response = model.generate_content(prompt)
        return response.text

class GeneralQAAgent(BaseAgent):
    """A generic agent for open-domain questions and answers."""
    def get_response(self, user_message: str, profile_data: dict) -> str:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are a helpful general knowledge assistant. Answer the user's question clearly and concisely.
        User's question: "{user_message}"
        """
        response = model.generate_content(prompt)
        return response.text
    
class NutriScanApp(ctk.CTk):
    def __init__(self):
        self.current_user = "user"  # ✅ defined before other calls
        super().__init__()
        logging.basicConfig(filename="nutriscan.log", level=logging.INFO)
        # --- Window Setup ---
        self.title("NutriScanAI Desktop Suite")
        self.geometry("1200x800")
        self.minsize(1100, 700)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # ✨ NEW: Setup placeholder photos for family members
        self.setup_member_photos()

        # --- Initialize Application State ---
        self.is_running = True  # Flag to track if the application is running
        self.protocol("WM_DELETE_WINDOW", self.on_closing)  # Handle window close

        # --- Initialize Profile Storage ---
        self.profile_data = self.load_profile()
        self.scanned_foods = self.profile_data.get("scanned_foods", [])  # Store scanned food data
        self.current_user = "user"

# --- Inside your __init__ method ---

        self.last_ai_response = "" # 🔊 Add this line

        # ✨ NEW: Initialize Voice Agent Components
        self.recognizer = sr.Recognizer()
        self.agents = {
            "Nutrition Coach": NutritionCoachAgent(),
            "General Q&A": GeneralQAAgent(),
        }
        self.current_agent = self.agents["Nutrition Coach"]
        
        # ✨ NEW: Initialize Health Community Database
        self.init_health_community_db()

        # --- Configure Gemini API --- # This line should already exist
        # --- Configure Gemini API ---
        api_key = os.getenv('AIzaSyBcEqG-Wx64WB8V5fW8qHAMLIhHkLth4Q4') or API_KEY
        if api_key:
            try:
                genai.configure(api_key=api_key)
                print("Gemini API configured successfully.")
            except Exception as e:
                print(f"API Key Error: {e}")
                self.set_status(f"API Key Error: {e}", "red")
        else:
            print("WARNING: Gemini API key is not set. AI features will not work.")
            self.set_status("Gemini API key missing. AI features disabled.", "red")

        # --- Start with the login screen ---
        self._create_login_screen()

    def on_closing(self):
        """Handle window close to prevent background errors."""
        self.is_running = False  # Set flag to stop background tasks
        try:
            self.destroy()  # Close the Tkinter window
        except Exception:
            pass  # Ignore errors during destruction

    def _clear_screen(self):
        """Destroys all widgets on the main window if application is running."""
        if not self.is_running:
            return
        for widget in self.winfo_children():
            widget.destroy()

    def set_status(self, message, color="default"):
        """Update status bar only if application is running."""
        if not self.is_running:
            return
        logging.info(f"Status: {message}")
        colors = {"blue": "#3B82F6", "green": "#22C55E", "red": "#EF4444", "default": "#242424"}
        try:
            self.status_bar.configure(text=message, fg_color=colors.get(color, "#242424"))
        except Exception:
            pass  # Ignore if status_bar is inaccessible

    # ===================================================================
    # SECTION 0: LOGIN FEATURE
    # ===================================================================
    def _create_login_screen(self):
        """Creates and displays the initial login widgets."""
        if not self.is_running:
            return
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        login_frame = ctk.CTkFrame(self, corner_radius=15)
        login_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        title_label = ctk.CTkLabel(login_frame, text="NutriScanAI Login", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(padx=50, pady=(40, 20))

        self.username_entry = ctk.CTkEntry(login_frame, placeholder_text="Username", width=250, height=40)
        self.username_entry.pack(padx=50, pady=10)
        self.username_entry.insert(0, "user")

        self.password_entry = ctk.CTkEntry(login_frame, placeholder_text="Password", show="*", width=250, height=40)
        self.password_entry.pack(padx=50, pady=10)
        self.password_entry.insert(0, "password")

        login_button = ctk.CTkButton(login_frame, text="Login", command=self._attempt_login, height=40)
        login_button.pack(padx=50, pady=20)
        self.bind("<Return>", lambda event: self._attempt_login())

        self.login_error_label = ctk.CTkLabel(login_frame, text="", text_color="red")
        self.login_error_label.pack(padx=50, pady=(0, 40))

    def _attempt_login(self):
        """Checks the entered username and password."""
        if not self.is_running:
            return
        username = self.username_entry.get()
        password = self.password_entry.get()

        if username == "user" and password == "password":
            self.current_user = username
            self.unbind("<Return>")
            self._clear_screen()
            self._create_main_app_ui()
        else:
            self.login_error_label.configure(text="Invalid username or password.")

    def logout(self):
        """Logs the user out and returns to the login screen."""
        if not self.is_running:
            return
        self._clear_screen()
        self._create_login_screen()

    # ===================================================================
    # SECTION 1: MAIN APPLICATION UI
    # ===================================================================
    def _create_main_app_ui(self):
        """Creates the main application interface after a successful login."""
        if not self.is_running:
            return
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        header_icon = ctk.CTkLabel(header_frame, text="🥗", font=("Segoe UI Emoji", 24))
        header_icon.pack(side="left", padx=(0, 10))
        
        header_label = ctk.CTkLabel(header_frame, text="NutriScanAI Suite", font=ctk.CTkFont(size=24, weight="bold"))
        header_label.pack(side="left")
        
        # Tab View
        self.tab_view = ctk.CTkTabview(self, corner_radius=10, border_width=1, fg_color="#2D3748",
                                       segmented_button_fg_color="#1F2937", segmented_button_selected_color="#3B82F6",
                                       segmented_button_selected_hover_color="#60A5FA", segmented_button_unselected_hover_color="#374151")
        self.tab_view.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.tab_view.add("Dashboard")
        self.tab_view.add("Scan & Analyze")
        self.tab_view.add("Health Report")
        self.tab_view.add("Health Profile")
        self.tab_view.add("Audit")
        self.tab_view.add("AI Coach")
        self.tab_view.add("Subscriptions")
        self.tab_view.add("Meal Planner")
        self.tab_view.add("Family Hub") 
        self.tab_view.add("Pain Relief & Exercises")  # NEW TAB
        self.tab_view.add("Health Community")  # NEW SOCIAL COMMUNITY TAB
        self.tab_view.add("Doctor Consultation")  # NEW DOCTOR CONSULTATION TAB
        self.tab_view.add("Buy Medicines")
        

        self.create_dashboard_tab(self.tab_view.tab("Dashboard"))
        self.create_analysis_tab(self.tab_view.tab("Scan & Analyze"))
        self.create_health_report_tab(self.tab_view.tab("Health Report"))
        self.create_health_profile_tab(self.tab_view.tab("Health Profile"))
        self.create_audit_tab(self.tab_view.tab("Audit"))
        self.create_coach_tab(self.tab_view.tab("AI Coach"))
        self.create_subscriptions_tab(self.tab_view.tab("Subscriptions"))
        self.create_meal_planner_tab(self.tab_view.tab("Meal Planner"))
        self.create_family_hub_tab(self.tab_view.tab("Family Hub")) 
        self.create_pain_relief_tab(self.tab_view.tab("Pain Relief & Exercises"))  # NEW TAB CREATION
        self.create_health_community_tab(self.tab_view.tab("Health Community"))  # NEW TAB CREATION
        self.create_doctor_consultation_tab(self.tab_view.tab("Doctor Consultation"))  # NEW TAB CREATION
        self.create_medicine_suggestions_tab(self.tab_view.tab("Buy Medicines"))
        


        # Bind tab change event to stop voice
        self.tab_view._segmented_button.configure(command=self.on_tab_change)

        self.status_bar = ctk.CTkLabel(self, text=f"Welcome back, {self.current_user}!", height=25, fg_color="#1F2937", text_color="#FFFFFF")
        self.status_bar.grid(row=2, column=0, padx=0, pady=0, sticky="ew")

    def on_tab_change(self, value):
        """Handle tab changes and stop voice if speaking"""
        # Stop voice when changing tabs
        self.stop_voice_on_tab_change()
        
        # Actually switch to the selected tab
        self.tab_view.set(value)
        
        # Update status
        self.set_status(f"Switched to {value} tab", "blue")


    # ===================================================================
    # TAB 1: Dashboard (Updated with Wearable Integration)
    # ===================================================================
    def create_dashboard_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(1, weight=3)
        tab.grid_columnconfigure(2, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar_frame = ctk.CTkFrame(tab, width=200, corner_radius=0, fg_color="#2c3e50")
        sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        sidebar_frame.grid_rowconfigure(5, weight=1)

        logo_label = ctk.CTkLabel(sidebar_frame, text="NutriScanAI", font=ctk.CTkFont(size=22, weight="bold"))
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))
        
        buttons = [
            ("🏠  Dashboard", lambda: self.tab_view.set("Dashboard")),
            ("📊  Analytics", lambda: self.set_status("Analytics not implemented", "blue")),
            ("⚙️  Settings", lambda: self.set_status("Settings not implemented", "blue")),
            ("⌚ Sync Wearables", self.sync_wearable_data)
        ]
        
        for i, (text, command) in enumerate(buttons):
            button = ctk.CTkButton(sidebar_frame, text=text, anchor="w", compound="left", corner_radius=8,
                                   fg_color="transparent", text_color="#bdc3c7", hover_color="#34495e",
                                   font=ctk.CTkFont(size=14), command=command)
            button.grid(row=i + 1, column=0, padx=10, pady=10, sticky="ew")

        logout_button = ctk.CTkButton(sidebar_frame, text="Logout", fg_color="#c0392b", hover_color="#e74c3c", command=self.logout)
        logout_button.grid(row=6, column=0, padx=10, pady=20, sticky="s")

        # Main Content Area
        main_content_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        main_content_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        main_content_frame.grid_columnconfigure((0, 1), weight=1)

        greeting_label = ctk.CTkLabel(main_content_frame, text=f"Good Morning, {self.current_user}!", font=ctk.CTkFont(size=28, weight="bold"), anchor="w")
        greeting_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")
        
        quote_label = ctk.CTkLabel(main_content_frame, text="\"The greatest wealth is health.\" - Virgil", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray", anchor="w")
        quote_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 20), sticky="ew")

        metrics_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        metrics_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        metrics_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        metrics_data = [
            ("Blood Pressure", self.profile_data.get("blood_pressure", "110/70"), "mmHg", "#8e44ad"),
            ("Heart Rate", self.profile_data.get("heart_rate", "83"), "BPM", "#27ae60"),
            ("Glucose", self.profile_data.get("glucose", "80"), "mg/dL", "#2980b9"),
            ("Steps", self.profile_data.get("steps", "8500"), "steps", "#e67e22")
        ]
        
        for i, (title, value, unit, color) in enumerate(metrics_data):
            metric_card = ctk.CTkFrame(metrics_frame, corner_radius=10)
            metric_card.grid(row=0, column=i, padx=10, sticky="nsew")
            value_label = ctk.CTkLabel(metric_card, text=value, font=ctk.CTkFont(size=28, weight="bold"), text_color=color)
            value_label.pack(pady=(15, 0), padx=10)
            unit_label = ctk.CTkLabel(metric_card, text=unit, font=ctk.CTkFont(size=12), text_color="gray")
            unit_label.pack()
            title_label = ctk.CTkLabel(metric_card, text=title, font=ctk.CTkFont(size=14))
            title_label.pack(pady=(0, 15), padx=10)
            
        # Activity Charts
        activity_frame = ctk.CTkFrame(main_content_frame, corner_radius=10)
        activity_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        activity_label = ctk.CTkLabel(activity_frame, text="Weekly Activity", font=ctk.CTkFont(size=16, weight="bold"))
        activity_label.pack(padx=20, pady=(10, 5))
        
        # Weekly Steps Chart
        fig_steps, ax_steps = plt.subplots(figsize=(5, 2.5), dpi=100)
        fig_steps.patch.set_facecolor('#2b2b2b')
        ax_steps.set_facecolor('#2b2b2b')
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        steps = self.profile_data.get("weekly_steps", [8500, 7200, 9800, 6500, 10500, 12300, 7800])
        ax_steps.bar(days, steps, color="#27ae60")
        ax_steps.tick_params(axis='x', colors='gray')
        ax_steps.tick_params(axis='y', colors='gray')
        ax_steps.spines['top'].set_visible(False)
        ax_steps.spines['right'].set_visible(False)
        ax_steps.spines['left'].set_color('gray')
        ax_steps.spines['bottom'].set_color('gray')
        fig_steps.tight_layout()
        
        canvas_steps = FigureCanvasTkAgg(fig_steps, master=activity_frame)
        canvas_steps.draw()
        canvas_steps.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)
        
        # Sleep and Heart Rate Chart
        sleep_hr_frame = ctk.CTkFrame(main_content_frame, corner_radius=10)
        sleep_hr_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        sleep_hr_label = ctk.CTkLabel(sleep_hr_frame, text="Sleep & Heart Rate Trends", font=ctk.CTkFont(size=16, weight="bold"))
        sleep_hr_label.pack(padx=20, pady=(10, 5))
        
        fig_sleep_hr, ax_sleep = plt.subplots(figsize=(5, 2.5), dpi=100)
        ax_heart = ax_sleep.twinx()
        fig_sleep_hr.patch.set_facecolor('#2b2b2b')
        ax_sleep.set_facecolor('#2b2b2b')
        sleep_data = self.profile_data.get("weekly_sleep", [7.5, 6.8, 8.0, 7.2, 6.5, 8.5, 7.0])
        heart_data = self.profile_data.get("weekly_heart_rate", [80, 82, 78, 85, 83, 79, 81])
        ax_sleep.plot(days, sleep_data, color="#3498db", label="Sleep (hrs)")
        ax_heart.plot(days, heart_data, color="#e74c3c", label="Heart Rate (bpm)")
        ax_sleep.set_ylabel("Sleep (hrs)", color="gray")
        ax_heart.set_ylabel("Heart Rate (bpm)", color="gray")
        ax_sleep.tick_params(axis='x', colors='gray')
        ax_sleep.tick_params(axis='y', colors='gray')
        ax_heart.tick_params(axis='y', colors='gray')
        ax_sleep.spines['top'].set_visible(False)
        ax_heart.spines['top'].set_visible(False)
        ax_sleep.spines['right'].set_visible(False)
        ax_heart.spines['left'].set_visible(False)
        ax_sleep.spines['left'].set_color('gray')
        ax_heart.spines['right'].set_color('gray')
        ax_sleep.spines['bottom'].set_color('gray')
        fig_sleep_hr.legend(loc="upper center", facecolor="#2b2b2b", edgecolor="gray", labelcolor="gray")
        fig_sleep_hr.tight_layout()
        
        canvas_sleep_hr = FigureCanvasTkAgg(fig_sleep_hr, master=sleep_hr_frame)
        canvas_sleep_hr.draw()
        canvas_sleep_hr.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=5)
        
        # Right Panel
        right_panel_frame = ctk.CTkFrame(tab, width=250, corner_radius=0, fg_color="transparent")
        right_panel_frame.grid(row=0, column=2, padx=(10, 20), pady=20, sticky="nsew")
        right_panel_frame.grid_rowconfigure(1, weight=1)

        calendar_frame = ctk.CTkFrame(right_panel_frame, corner_radius=10)
        calendar_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        now = datetime.datetime.now()
        cal_title = ctk.CTkLabel(calendar_frame, text=now.strftime("%B %Y"), font=ctk.CTkFont(size=16, weight="bold"))
        cal_title.pack(pady=10)
        
        cal_str = calendar.month(now.year, now.month)
        calendar_text = ctk.CTkLabel(calendar_frame, text=cal_str, font=("Courier", 12), justify="left")
        calendar_text.pack(padx=10, pady=(0, 10))

        appointments_frame = ctk.CTkFrame(right_panel_frame, corner_radius=10)
        appointments_frame.grid(row=1, column=0, sticky="nsew", pady=10)
        appointments_label = ctk.CTkLabel(appointments_frame, text="Today's Appointments", font=ctk.CTkFont(size=16, weight="bold"))
        appointments_label.pack(pady=10, padx=15)
        
        appointment_texts = ["10:00 AM - Dr. John Doe", "02:30 PM - Dental Check-up"]
        for text in appointment_texts:
            ctk.CTkLabel(appointments_frame, text=f"• {text}", anchor="w").pack(fill="x", padx=15, pady=5)

    def sync_wearable_data(self):
        """Simulates syncing data from wearable devices and updates profile."""
        if not self.is_running:
            return
        self.set_status("Syncing wearable data...", "blue")
        threading.Thread(target=self.fetch_wearable_data).start()

    def fetch_wearable_data(self):
        """Mock API call to fetch wearable data."""
        if not self.is_running:
            return
        try:
            wearable_data = {
                "steps": str(random.randint(7000, 15000)),
                "heart_rate": str(random.randint(70, 90)),
                "glucose": str(random.randint(70, 100)),
                "blood_pressure": f"{random.randint(100, 130)}/{random.randint(60, 80)}",
                "weekly_steps": [random.randint(5000, 15000) for _ in range(7)],
                "weekly_sleep": [round(random.uniform(6.0, 9.0), 1) for _ in range(7)],
                "weekly_heart_rate": [random.randint(70, 90) for _ in range(7)]
            }
            self.profile_data.update(wearable_data)
            self.save_profile()
            if self.is_running:
                self.after(0, self.refresh_dashboard)
                self.after(0, self.set_status, "Wearable data synced successfully.", "green")
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error syncing wearable data: {e}", "red")

    def refresh_dashboard(self):
        """Refreshes the Dashboard tab to reflect updated wearable data."""
        if not self.is_running:
            return
        self._clear_screen()
        self._create_main_app_ui()
        self.tab_view.set("Dashboard")

    # ===================================================================
    # TAB 2: Scan & Analyze
    # ===================================================================
    def create_analysis_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkFrame(tab, fg_color="transparent")
        left_panel.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        
        self.select_button = ctk.CTkButton(left_panel, text="Select Food Image", command=self.select_image_and_start_analysis, fg_color="#3B82F6", hover_color="#60A5FA")
        self.select_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.image_label = ctk.CTkLabel(left_panel, text="Your selected image will appear here", corner_radius=10, fg_color="#2B2B2B")
        self.image_label.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        right_panel = ctk.CTkFrame(tab, fg_color="transparent")
        right_panel.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)
        
        # Create scrollable frame for the right panel content
        self.right_scroll_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.right_scroll_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.right_scroll_frame.grid_columnconfigure(0, weight=1)
        
        results_label = ctk.CTkLabel(self.right_scroll_frame, text="Nutritional Analysis", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF")
        results_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Rating System Frame
        self.rating_frame = ctk.CTkFrame(self.right_scroll_frame, corner_radius=10, fg_color="#2B2B2B")
        self.rating_frame.grid(row=1, column=0, sticky="ew", pady=10)
        self.rating_frame.grid_columnconfigure(1, weight=1)
        
        # Rating Header
        rating_header = ctk.CTkLabel(self.rating_frame, text="🍎 Nutritional Rating", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF")
        rating_header.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        
        # Rating Score
        self.rating_score_label = ctk.CTkLabel(self.rating_frame, text="--", font=ctk.CTkFont(size=24, weight="bold"), text_color="#FFFFFF")
        self.rating_score_label.grid(row=1, column=0, padx=15, pady=5, sticky="w")
        
        # Rating Category
        self.rating_category_label = ctk.CTkLabel(self.rating_frame, text="--", font=ctk.CTkFont(size=14), text_color="#D1D5DB")
        self.rating_category_label.grid(row=1, column=1, padx=15, pady=5, sticky="w")
        
        # Rating Progress Bar
        self.rating_progress = ctk.CTkProgressBar(self.rating_frame, progress_color="#3B82F6")
        self.rating_progress.set(0)
        self.rating_progress.grid(row=2, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")
        
        # Rating Legend
        legend_frame = ctk.CTkFrame(self.rating_frame, fg_color="transparent")
        legend_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew")
        legend_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        legend_items = [
            ("0-25", "Poor", "#EF4444"),
            ("26-50", "Fair", "#F59E0B"),
            ("51-75", "Good", "#22C55E"),
            ("76-100", "Excellent", "#3B82F6")
        ]
        
        for i, (range_text, category, color) in enumerate(legend_items):
            legend_item = ctk.CTkFrame(legend_frame, fg_color="transparent")
            legend_item.grid(row=0, column=i, padx=2)
            
            range_label = ctk.CTkLabel(legend_item, text=range_text, font=ctk.CTkFont(size=10, weight="bold"), text_color=color)
            range_label.pack()
            category_label = ctk.CTkLabel(legend_item, text=category, font=ctk.CTkFont(size=8), text_color="#9CA3AF")
            category_label.pack()
        
        # Basic Nutrition Info Frame
        self.results_frame = ctk.CTkFrame(self.right_scroll_frame, corner_radius=10, fg_color="#2B2B2B")
        self.results_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.results_frame.grid_columnconfigure(1, weight=1)
        self.result_widgets = {}
        fields = ["Name", "Calories", "Protein", "Carbs", "Fat"]
        for i, field in enumerate(fields):
            label = ctk.CTkLabel(self.results_frame, text=f"{field}:", font=ctk.CTkFont(weight="bold"), text_color="#FFFFFF")
            label.grid(row=i, column=0, padx=15, pady=10, sticky="w")
            value = ctk.CTkLabel(self.results_frame, text="-", anchor="w", wraplength=200, text_color="#D1D5DB")
            value.grid(row=i, column=1, padx=15, pady=10, sticky="ew")
            self.result_widgets[field.lower()] = value
        
        # Health Benefits & Concerns Frame
        self.health_frame = ctk.CTkFrame(self.right_scroll_frame, corner_radius=10, fg_color="#2B2B2B")
        self.health_frame.grid(row=3, column=0, sticky="ew", pady=10)
        self.health_frame.grid_columnconfigure(1, weight=1)
        
        health_header = ctk.CTkLabel(self.health_frame, text="💚 Health Insights", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF")
        health_header.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")
        
        # Benefits
        benefits_label = ctk.CTkLabel(self.health_frame, text="Benefits:", font=ctk.CTkFont(weight="bold"), text_color="#22C55E")
        benefits_label.grid(row=1, column=0, padx=15, pady=5, sticky="w")
        self.benefits_text = ctk.CTkLabel(self.health_frame, text="-", anchor="w", wraplength=300, text_color="#D1D5DB")
        self.benefits_text.grid(row=1, column=1, padx=15, pady=5, sticky="ew")
        
        # Concerns
        concerns_label = ctk.CTkLabel(self.health_frame, text="Concerns:", font=ctk.CTkFont(weight="bold"), text_color="#EF4444")
        concerns_label.grid(row=2, column=0, padx=15, pady=5, sticky="w")
        self.concerns_text = ctk.CTkLabel(self.health_frame, text="-", anchor="w", wraplength=300, text_color="#D1D5DB")
        self.concerns_text.grid(row=2, column=1, padx=15, pady=5, sticky="ew")
        
        # Recommendations
        rec_label = ctk.CTkLabel(self.health_frame, text="Recommendations:", font=ctk.CTkFont(weight="bold"), text_color="#3B82F6")
        rec_label.grid(row=3, column=0, padx=15, pady=5, sticky="w")
        self.recommendations_text = ctk.CTkLabel(self.health_frame, text="-", anchor="w", wraplength=300, text_color="#D1D5DB")
        self.recommendations_text.grid(row=3, column=1, padx=15, pady=5, sticky="ew")
        
        notes_label = ctk.CTkLabel(self.right_scroll_frame, text="Notes", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF")
        notes_label.grid(row=4, column=0, sticky="w", pady=(10, 5))
        self.notes_textbox = ctk.CTkTextbox(self.right_scroll_frame, corner_radius=10, state="disabled", fg_color="#2B2B2B", text_color="#D1D5DB")
        self.notes_textbox.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        
        self.micronutrients_scroll_frame = ctk.CTkScrollableFrame(self.right_scroll_frame, corner_radius=10, fg_color="#2B2B2B")
        self.micronutrients_scroll_frame.grid(row=6, column=0, sticky="ew", pady=10)
        self.micronutrients_scroll_frame.grid_columnconfigure(1, weight=1)

    def select_image_and_start_analysis(self):
        if not self.is_running:
            return
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not file_path:
            return
        self.display_image(file_path)
        self.set_status("Analyzing Image & Generating Rating...", "blue")
        self.clear_results()
        self.select_button.configure(state="disabled")
        analysis_thread = threading.Thread(target=self.run_image_analysis_in_thread, args=(file_path,))
        analysis_thread.start()

    def display_image(self, file_path):
        if not self.is_running:
            return
        try:
            original_image = Image.open(file_path)
            widget_width = self.image_label.winfo_width()
            widget_height = self.image_label.winfo_height()
            
            display_image = original_image.copy()
            display_image.thumbnail((widget_width - 20, widget_height - 20))
            
            ctk_image = ctk.CTkImage(light_image=display_image, dark_image=display_image, size=display_image.size)
            self.image_label.configure(image=ctk_image, text="")
        except Exception as e:
            if self.is_running:
                self.image_label.configure(text=f"Error displaying image:\n{e}", image=None)

    def clear_results(self):
        if not self.is_running:
            return
        # Clear basic nutrition info
        for key, widget in self.result_widgets.items():
            widget.configure(text="-")
        
        # Clear rating system
        self.rating_score_label.configure(text="--")
        self.rating_category_label.configure(text="--")
        self.rating_progress.set(0)
        
        # Clear health insights
        self.benefits_text.configure(text="-")
        self.concerns_text.configure(text="-")
        self.recommendations_text.configure(text="-")
        
        # Clear notes
        self.notes_textbox.configure(state="normal")
        self.notes_textbox.delete("1.0", "end")
        self.notes_textbox.configure(state="disabled")
        
        # Clear micronutrients
        for widget in self.micronutrients_scroll_frame.winfo_children():
            widget.destroy()

    def run_image_analysis_in_thread(self, file_path):
        if not self.is_running:
            return
        try:
            img = Image.open(file_path)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            results = self.get_image_analysis(img_byte_arr.getvalue())
            if self.is_running:
                self.after(0, self.update_analysis_ui, results)
        except Exception as e:
            if self.is_running:
                self.after(0, self.update_analysis_ui, {"error": str(e)})

    def get_image_analysis(self, image_bytes: bytes):
        print("Attempting image analysis with Gemini API...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}
        prompt = """
        You are NutriScanAI, an expert nutritionist. Analyze this image of a food item.
        Respond ONLY with a valid JSON object in the format:
        {
          "name": "string",
          "calories": "string",
          "protein": "string",
          "carbs": "string",
          "fat": "string",
          "micronutrients": [
            {"name": "string", "value": "string"}
          ],
          "notes": "string",
          "nutritional_rating": number (0-100),
          "rating_category": "string (Poor/Fair/Good/Excellent)",
          "health_benefits": ["string"],
          "health_concerns": ["string"],
          "recommendations": ["string"]
        }
        
        For the nutritional_rating (0-100):
        - 0-25: Poor - Not recommended for regular consumption
        - 26-50: Fair - Consume in moderation
        - 51-75: Good - Healthy choice with some benefits
        - 76-100: Excellent - Highly nutritious and recommended
        
        Consider factors like:
        - Nutritional density
        - Presence of harmful ingredients
        - Processing level
        - Sugar/sodium content
        - Presence of beneficial nutrients
        - Overall health impact
        
        Ensure that the micronutrients list includes at least Iron, Calcium, Vitamin D, Vitamin B12, Folate (Vitamin B9), Zinc, Magnesium, Vitamin A if they are present in the food item, and add any other significant micronutrients as appropriate.
        """
        try:
            response = model.generate_content([prompt, image_part])
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            print(f"API Response: {json_text}")
            results = json.loads(json_text)
            return results
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return {"error": f"Gemini API Error: {e}"}

    def get_rating_color(self, rating):
        """Get the color for a given rating value."""
        if rating <= 25:
            return "#EF4444"  # Red for Poor
        elif rating <= 50:
            return "#F59E0B"  # Orange for Fair
        elif rating <= 75:
            return "#22C55E"  # Green for Good
        else:
            return "#3B82F6"  # Blue for Excellent

    def get_rating_emoji(self, rating):
        """Get the emoji for a given rating value."""
        if rating <= 25:
            return "❌"  # Poor
        elif rating <= 50:
            return "⚠️"  # Fair
        elif rating <= 75:
            return "✅"  # Good
        else:
            return "🌟"  # Excellent

    def get_fallback_rating_data(self, food_name):
        """Get fallback rating data for common foods when AI analysis fails."""
        fallback_data = {
            # Excellent Foods (76-100)
            "apple": {"rating": 85, "category": "Excellent", "benefits": ["High in fiber", "Rich in antioxidants", "Low calorie"], "concerns": ["Natural sugars"], "recommendations": ["Great daily fruit choice", "Eat with skin for maximum benefits"]},
            "salad": {"rating": 90, "category": "Excellent", "benefits": ["Low in calories", "High in fiber", "Rich in vitamins"], "concerns": ["May be low in protein"], "recommendations": ["Add protein source", "Use healthy dressing"]},
            "spinach": {"rating": 95, "category": "Excellent", "benefits": ["High in iron", "Rich in vitamins", "Low calorie"], "concerns": ["May contain oxalates"], "recommendations": ["Excellent daily vegetable", "Great for salads and smoothies"]},
            "broccoli": {"rating": 88, "category": "Excellent", "benefits": ["High in fiber", "Rich in vitamins C and K", "Antioxidant properties"], "concerns": ["May cause gas"], "recommendations": ["Steam lightly to preserve nutrients", "Great addition to meals"]},
            "salmon": {"rating": 92, "category": "Excellent", "benefits": ["High in omega-3", "Excellent protein source", "Rich in vitamins"], "concerns": ["May contain mercury"], "recommendations": ["Choose wild-caught", "2-3 servings per week"]},
            
            # Good Foods (51-75)
            "banana": {"rating": 75, "category": "Good", "benefits": ["High in potassium", "Good source of energy", "Rich in vitamins"], "concerns": ["High in natural sugars"], "recommendations": ["Good pre-workout snack", "Moderate consumption"]},
            "chicken": {"rating": 70, "category": "Good", "benefits": ["High in protein", "Low in fat", "Good source of B vitamins"], "concerns": ["May contain antibiotics"], "recommendations": ["Choose organic when possible", "Good protein source"]},
            "rice": {"rating": 60, "category": "Good", "benefits": ["Good energy source", "Gluten-free"], "concerns": ["High in carbs", "Low in fiber"], "recommendations": ["Choose brown rice", "Moderate portions"]},
            "yogurt": {"rating": 65, "category": "Good", "benefits": ["Good source of protein", "Contains probiotics", "High in calcium"], "concerns": ["May contain added sugars"], "recommendations": ["Choose plain Greek yogurt", "Add fresh fruits"]},
            
            # Fair Foods (26-50)
            "chocolate": {"rating": 35, "category": "Fair", "benefits": ["Contains antioxidants", "Mood booster"], "concerns": ["High in sugar and fat", "High calories"], "recommendations": ["Choose dark chocolate", "Consume in moderation"]},
            "noodles": {"rating": 30, "category": "Fair", "benefits": ["Quick energy source"], "concerns": ["High in refined carbs", "Low in fiber"], "recommendations": ["Choose whole grain noodles", "Add vegetables"]},
            "bread": {"rating": 40, "category": "Fair", "benefits": ["Good energy source", "Contains some fiber"], "concerns": ["High in carbs", "May contain preservatives"], "recommendations": ["Choose whole grain bread", "Moderate consumption"]},
            "cheese": {"rating": 45, "category": "Fair", "benefits": ["High in protein", "Good source of calcium"], "concerns": ["High in saturated fat", "High in sodium"], "recommendations": ["Choose low-fat varieties", "Use in moderation"]},
            
            # Poor Foods (0-25)
            "pizza": {"rating": 25, "category": "Poor", "benefits": ["Contains some protein"], "concerns": ["High in calories", "High in sodium", "High in saturated fat"], "recommendations": ["Limit consumption", "Choose healthier toppings"]},
            "maggie": {"rating": 20, "category": "Poor", "benefits": ["Quick to prepare", "Inexpensive"], "concerns": ["High in sodium", "Low in nutrients", "Processed ingredients"], "recommendations": ["Not recommended for regular consumption", "Choose whole grain alternatives"]},
            "burger": {"rating": 15, "category": "Poor", "benefits": ["Contains protein"], "concerns": ["High in calories", "High in saturated fat", "High in sodium"], "recommendations": ["Limit consumption", "Choose lean meat options"]},
            "fries": {"rating": 10, "category": "Poor", "benefits": ["Quick energy source"], "concerns": ["High in calories", "High in unhealthy fats", "High in sodium"], "recommendations": ["Avoid regular consumption", "Choose baked alternatives"]},
            "soda": {"rating": 5, "category": "Poor", "benefits": ["Provides quick energy"], "concerns": ["High in sugar", "No nutritional value", "Can cause health issues"], "recommendations": ["Avoid consumption", "Choose water or herbal tea"]}
        }
        
        # Try to match food name with fallback data
        food_lower = food_name.lower()
        for key, data in fallback_data.items():
            if key in food_lower:
                return data
        
        # Default fallback for unknown foods
        return {"rating": 50, "category": "Fair", "benefits": ["Moderate nutritional value"], "concerns": ["Limited information available"], "recommendations": ["Consume in moderation"]}

    def update_analysis_ui(self, results):
        if not self.is_running:
            return
        self.select_button.configure(state="normal")
        logging.info("Select Food Image button re-enabled")
        if "error" not in results:
            self.scanned_foods.append(results)
            self.save_profile()
        if "error" in results:
            print(f"Error: {results['error']}")
            return
        
        # Update basic nutrition info
        for key, widget in self.result_widgets.items():
            widget.configure(text=results.get(key, "-"))
        
        # Update rating system
        rating = results.get("nutritional_rating", 0)
        category = results.get("rating_category", "Unknown")
        benefits = results.get("health_benefits", [])
        concerns = results.get("health_concerns", [])
        recommendations = results.get("recommendations", [])
        
        # Use fallback data if AI didn't provide rating information
        if rating == 0 or category == "Unknown":
            food_name = results.get("name", "Unknown Food")
            fallback_data = self.get_fallback_rating_data(food_name)
            rating = fallback_data["rating"]
            category = fallback_data["category"]
            if not benefits:
                benefits = fallback_data["benefits"]
            if not concerns:
                concerns = fallback_data["concerns"]
            if not recommendations:
                recommendations = fallback_data["recommendations"]
        
        # Get rating color and emoji
        rating_color = self.get_rating_color(rating)
        rating_emoji = self.get_rating_emoji(rating)
        
        # Set rating score and category with emoji
        self.rating_score_label.configure(text=f"{rating_emoji} {rating}/100", text_color=rating_color)
        self.rating_category_label.configure(text=f"{category}", text_color=rating_color)
        
        # Set progress bar
        progress_value = rating / 100.0
        self.rating_progress.set(progress_value)
        self.rating_progress.configure(progress_color=rating_color)
        
        # Update health insights
        self.benefits_text.configure(text=", ".join(benefits) if benefits else "No specific benefits identified")
        self.concerns_text.configure(text=", ".join(concerns) if concerns else "No major concerns identified")
        self.recommendations_text.configure(text=", ".join(recommendations) if recommendations else "No specific recommendations")
        
        # Update notes
        self.notes_textbox.configure(state="normal")
        self.notes_textbox.delete("1.0", "end")
        self.notes_textbox.insert("1.0", results.get("notes", "No notes available."))
        self.notes_textbox.configure(state="disabled")
        
        # Update micronutrients
        for widget in self.micronutrients_scroll_frame.winfo_children():
            widget.destroy()
        if "micronutrients" in results and results["micronutrients"]:
            for i, micronutrient in enumerate(results["micronutrients"]):
                name_label = ctk.CTkLabel(
                    self.micronutrients_scroll_frame,
                    text=f"{micronutrient['name']}:",
                    font=ctk.CTkFont(weight="bold"),
                    text_color="#FFFFFF"
                )
                name_label.grid(row=i, column=0, padx=15, pady=5, sticky="w")
                value_label = ctk.CTkLabel(
                    self.micronutrients_scroll_frame,
                    text=micronutrient['value'],
                    anchor="w",
                    wraplength=200,
                    text_color="#D1D5DB"
                )
                value_label.grid(row=i, column=1, padx=15, pady=5, sticky="ew")
        else:
            no_data_label = ctk.CTkLabel(
                self.micronutrients_scroll_frame,
                text="Micronutrient data not available.",
                anchor="w",
                text_color="#D1D5DB"
            )
            no_data_label.grid(row=0, column=0, columnspan=2, padx=15, pady=5, sticky="ew")
        
        print("Image analysis complete.")
        self.set_status("Analysis complete! Check the nutritional rating and recommendations.", "green")



    # ===================================================================
    # TAB 3: Health Report
    # ===================================================================
    def create_health_report_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        toolbar_frame = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar_frame.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        input_options = [
            ("📄 Upload PDF", self.upload_pdf_report),
            ("🖼️ Upload Image", self.upload_image_report),
            ("📷 Capture Photo", self.capture_photo),
            ("✍️ Enter Text", self.open_text_input_dialog)
        ]
        for i, (text, command) in enumerate(input_options):
            button = ctk.CTkButton(toolbar_frame, text=text, command=command, width=150, height=40,
                                   font=ctk.CTkFont(size=14), compound="left", fg_color="#3B82F6", hover_color="#60A5FA")
            button.grid(row=0, column=i, padx=5, pady=5)
        content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        content_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=2)
        content_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2B2B2B")
        self.preview_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="Preview of uploaded report will appear here", 
                                        font=ctk.CTkFont(size=14), wraplength=200, text_color="#D1D5DB")
        self.preview_label.pack(fill="both", expand=True, padx=10, pady=10)
        chat_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2B2B2B")
        chat_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)
        self.report_chat_textbox = ctk.CTkTextbox(chat_frame, corner_radius=10, state="disabled",
                                                font=("Arial", 14), wrap="word", fg_color="#2B2B2B", text_color="#FFFFFF")
        self.report_chat_textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.report_chat_textbox.tag_config("user", foreground="white", lmargin1=20, lmargin2=20, rmargin=20, spacing1=10, spacing3=10)
        self.report_chat_textbox.tag_config("ai", foreground="#3b82f6", lmargin1=20, lmargin2=20, rmargin=20, spacing1=10, spacing3=10)
        self.report_chat_textbox.tag_config("ai_card", background="#34495e", lmargin1=30, lmargin2=30, rmargin=30, spacing1=15, spacing3=15)
        input_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        input_frame.grid_columnconfigure(0, weight=1)
        self.report_chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Ask a follow-up question...")
        self.report_chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.report_chat_entry.bind("<Return>", lambda event: self.send_report_chat_message(event))
        self.report_send_button = ctk.CTkButton(input_frame, text="Send", width=100, command=self.send_report_chat_message, fg_color="#3B82F6", hover_color="#60A5FA")
        self.report_send_button.grid(row=0, column=1)
        action_frame = ctk.CTkFrame(chat_frame, fg_color="transparent")
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkButton(action_frame, text="Ask More Questions", command=lambda: self.report_chat_entry.focus(), fg_color="#3B82F6", hover_color="#60A5FA").grid(row=0, column=0, padx=5)
        ctk.CTkButton(action_frame, text="Regenerate Routine", command=self.regenerate_routine, fg_color="#3B82F6", hover_color="#60A5FA").grid(row=0, column=1, padx=5)
        self.update_report_chat("AI Health Analyst", "Upload a health report to begin analysis.", is_ai=True)

    def upload_pdf_report(self):
        if not self.is_running:
            return
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return
        self.display_preview(file_path, is_pdf=True)
        self.set_status("Extracting text from PDF...", "blue")
        threading.Thread(target=self.process_pdf_report, args=(file_path,)).start()

    def upload_image_report(self):
        if not self.is_running:
            return
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not file_path:
            return
        self.display_preview(file_path)
        self.set_status("Performing OCR on image...", "blue")
        threading.Thread(target=self.process_image_report, args=(file_path,)).start()

    def capture_photo(self):
        if not self.is_running:
            return
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.set_status("Error: Could not access camera.", "red")
            return
        ret, frame = cap.read()
        cap.release()
        if ret:
            temp_path = "temp_capture.jpg"
            cv2.imwrite(temp_path, frame)
            self.display_preview(temp_path)
            self.set_status("Performing OCR on captured photo...", "blue")
            threading.Thread(target=self.process_image_report, args=(temp_path,)).start()
        else:
            self.set_status("Error: Failed to capture photo.", "red")

    def open_text_input_dialog(self):
        if not self.is_running:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Enter Health Report Text")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()
        text_area = ctk.CTkTextbox(dialog, height=300, wrap="word")
        text_area.pack(padx=20, pady=20, fill="both", expand=True)
        submit_button = ctk.CTkButton(dialog, text="Submit", command=lambda: self.process_manual_text(text_area.get("1.0", "end").strip(), dialog), fg_color="#3B82F6", hover_color="#60A5FA")
        submit_button.pack(pady=10)

    def process_manual_text(self, text, dialog):
        if not self.is_running:
            dialog.destroy()
            return
        dialog.destroy()
        self.set_status("Analyzing entered text...", "blue")
        threading.Thread(target=self.analyze_health_report, args=(text,)).start()

    def process_pdf_report(self, file_path):
        if not self.is_running:
            return
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            if self.is_running:
                self.after(0, self.analyze_health_report, text)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error extracting PDF: {e}", "red")

    def process_image_report(self, file_path):
        if not self.is_running:
            return
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            if self.is_running:
                self.after(0, self.analyze_health_report, text)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error performing OCR: {e}", "red")


    # ⬇️ Paste here
    def analyze_health_report(self, text):
        if not self.is_running:
            return
        try:
            analysis = self.get_health_report_analysis(text)
            if self.is_running:
                self.after(0, self.display_health_analysis, analysis)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error analyzing health report: {e}", "red")

    def analyze_health_report(self, text):
        if not self.is_running:
            return
        try:
            analysis = self.get_health_report_analysis(text)
            if self.is_running:
                self.after(0, self.display_health_analysis, analysis)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error analyzing health report: {e}", "red")


    def get_health_report_analysis(self, text):
        # 🔧 Sanitize text to avoid f-string format errors
        safe_text = (
            text.replace("{", "(")
                .replace("}", ")")
                .replace("%", " percent")
        )

        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            "You are a health analyst AI for NutriScanAI. Analyze the following health report text and provide:\n"
            "- A summary of key findings\n"
            "- Recommended over-the-counter products or supplements\n"
            "- A daily routine plan (diet and exercise)\n"
            "Respond in JSON format:\n"
            "```json\n"
            "{\n"
            '    \"summary\": \"...\",\n'
            '    \"products\": [\"product1\", \"product2\", ...],\n'
            '    \"routine\": {\n'
            '        \"diet\": \"...\",\n'
            '        \"exercise\": \"...\"\n'
            "    }\n"
            "}\n"
            "```\n"
            f"Health report text: \"{safe_text}\"\n"
        )

        try:
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_text)
        except Exception as e:
            # Fallback mock response in case of AI error
            return {
                "summary": "Your blood test shows slightly elevated cholesterol and low Vitamin D levels.",
                "products": ["Vitamin D3 2000 IU", "Omega-3 Fish Oil"],
                "routine": {
                    "diet": "Incorporate more leafy greens and fatty fish. Reduce saturated fats.",
                    "exercise": "30 minutes of brisk walking daily, 3 strength training sessions per week."
                }
            }


    def display_health_analysis(self, analysis):
        if not self.is_running:
            return
        self.report_chat_textbox.configure(state="normal")
        self.report_chat_textbox.delete("end-2l", "end")
        self.report_chat_textbox.insert("end", "Health Analysis Summary\n", ("ai", "ai_card"))
        self.report_chat_textbox.insert("end", f"{analysis['summary']}\n\n", ("ai", "ai_card"))
        self.report_chat_textbox.insert("end", "Recommended Products\n", ("ai", "ai_card"))
        for product in analysis['products']:
            self.report_chat_textbox.insert("end", f"• {product}\n", ("ai", "ai_card"))
        self.report_chat_textbox.insert("end", "\n")
        self.report_chat_textbox.insert("end", "Daily Routine Plan\n", ("ai", "ai_card"))
        self.report_chat_textbox.insert("end", f"Diet: {analysis['routine']['diet']}\n", ("ai", "ai_card"))
        self.report_chat_textbox.insert("end", f"Exercise: {analysis['routine']['exercise']}\n", ("ai", "ai_card"))
        print(f"Summary: {analysis['summary']}")
        print(f"Diet: {analysis['routine']['diet']}")
        print(f"Exercise: {analysis['routine']['exercise']}")
        self.report_chat_textbox.configure(state="disabled")
        self.report_chat_textbox.yview_moveto(1.0)
        self.set_status("Health report analysis complete.", "green")

    def send_report_chat_message(self, event=None):
        if not self.is_running:
            return
        message = self.report_chat_entry.get().strip()
        if not message:
            return
        self.update_report_chat("You", message)
        self.report_chat_entry.delete(0, "end")
        self.report_chat_entry.configure(state="disabled")
        self.report_send_button.configure(state="disabled")
        self.set_status("Processing your question...", "blue")
        threading.Thread(target=self.process_report_question, args=(message,)).start()

    def process_report_question(self, message):
        if not self.is_running:
            return
        try:
            response = self.get_gemini_coach_response(message)
            if self.is_running:
                self.after(0, self.update_report_chat, "AI Health Analyst", response, True)
        except Exception as e:
            if self.is_running:
                self.after(0, self.update_report_chat, "AI Health Analyst", f"Error: {e}", True)
        finally:
            if self.is_running:
                self.after(0, self.enable_report_chat_input)

    def regenerate_routine(self):
        if not self.is_running:
            return
        self.set_status("Regenerating routine...", "blue")
        self.update_report_chat("AI Health Analyst", "Generating new routine...", is_ai=True, is_loading=True)
        threading.Thread(target=self.display_health_analysis, args=(self.get_health_report_analysis("Regenerate routine"),)).start()

    def update_report_chat(self, sender, message, is_ai=False, is_loading=False):
        if not self.is_running:
            return
        self.report_chat_textbox.configure(state="normal")
        tag = "ai" if is_ai else "user"
        prefix = f"{sender}: "
        if is_loading:
            self.report_chat_textbox.insert("end", prefix + "Typing...\n", (tag,))
        else:
            self.report_chat_textbox.insert("end", prefix + message + "\n\n", (tag, "ai_card" if is_ai else ""))
        self.report_chat_textbox.configure(state="disabled")
        self.report_chat_textbox.yview_moveto(1.0)

    def enable_report_chat_input(self):
        if not self.is_running:
            return
        self.report_chat_entry.configure(state="normal")
        self.report_send_button.configure(state="normal")
        self.set_status("Ready", "default")

    def display_preview(self, file_path, is_pdf=False):
        if not self.is_running:
            return
        try:
            if is_pdf:
                self.preview_label.configure(text="PDF Preview (First page not shown)", image=None)
            else:
                img = Image.open(file_path)
                img.thumbnail((200, 200))
                ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.preview_label.configure(image=ctk_image, text="")
        except Exception as e:
            if self.is_running:
                self.preview_label.configure(text=f"Error displaying preview: {e}", image=None)

    # ===================================================================
    # TAB 4: Health Profile
    # ===================================================================
    def load_profile(self):
        try:
            if os.path.exists("profile.json"):
                with open("profile.json", "r") as f:
                    return json.load(f)
            return {
                "name": self.current_user,
                "age": "",
                "height": "",
                "weight": "",
                "conditions": "",
                "allergies": "",
                "goals": "",
                "steps": "8500",
                "heart_rate": "83",
                "glucose": "80",
                "blood_pressure": "110/70",
                "weekly_steps": [8500, 7200, 9800, 6500, 10500, 12300, 7800],
                "weekly_sleep": [7.5, 6.8, 8.0, 7.2, 6.5, 8.5, 7.0],
                "weekly_heart_rate": [80, 82, 78, 85, 83, 79, 81],
                "scanned_foods": []
            }
        except Exception as e:
            print(f"Error loading profile: {e}")
            self.set_status(f"Error loading profile: {e}", "red")
            return {
                "name": self.current_user,
                "age": "",
                "height": "",
                "weight": "",
                "conditions": "",
                "allergies": "",
                "goals": "",
                "steps": "8500",
                "heart_rate": "83",
                "glucose": "80",
                "blood_pressure": "110/70",
                "weekly_steps": [8500, 7200, 9800, 6500, 10500, 12300, 7800],
                "weekly_sleep": [7.5, 6.8, 8.0, 7.2, 6.5, 8.5, 7.0],
                "weekly_heart_rate": [80, 82, 78, 85, 83, 79, 81],
                "scanned_foods": []
            }

    def save_profile(self):
        if not self.is_running:
            return
        self.profile_data["scanned_foods"] = self.scanned_foods
        try:
            with open("profile.json", "w") as f:
                json.dump(self.profile_data, f, indent=4)
            self.set_status("Profile saved successfully.", "green")
        except Exception as e:
            self.set_status(f"Error saving profile: {e}", "red")

    def create_health_profile_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        profile_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2D3748")
        profile_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        profile_frame.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(profile_frame, text="Your Health Profile", font=ctk.CTkFont(size=18, weight="bold"), text_color="#FFFFFF")
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        fields = [
            ("Name", "name"),
            ("Age", "age"),
            ("Height (cm)", "height"),
            ("Weight (kg)", "weight"),
            ("Conditions", "conditions"),
            ("Allergies", "allergies"),
            ("Goals", "goals")
        ]
        self.profile_entries = {}
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(profile_frame, text=label, text_color="#FFFFFF").grid(row=i + 1, column=0, padx=(20, 10), pady=5, sticky="w")
            entry = ctk.CTkEntry(profile_frame, width=300, fg_color="#1F2937", text_color="#FFFFFF")
            entry.grid(row=i + 1, column=1, padx=(10, 20), pady=5, sticky="w")
            entry.insert(0, self.profile_data.get(key, ""))
            self.profile_entries[key] = entry
        save_button = ctk.CTkButton(profile_frame, text="Save Profile", command=self.update_profile, fg_color="#3B82F6", hover_color="#60A5FA")
        save_button.grid(row=len(fields) + 1, column=0, columnspan=2, padx=20, pady=20)

    def update_profile(self):
        if not self.is_running:
            return
        for key, entry in self.profile_entries.items():
            self.profile_data[key] = entry.get()
        self.save_profile()

      # ===================================================================
    # TAB 5: Audit
    # ===================================================================
    def create_audit_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        audit_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2D3748")
        audit_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        audit_frame.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(audit_frame, text="Home Product Audit", font=ctk.CTkFont(size=24, weight="bold"), text_color="#FFFFFF")
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        upload_button = ctk.CTkButton(audit_frame, text="Upload Product Images", command=self.upload_audit_images, height=40, fg_color="#10b981", hover_color="#059669")
        upload_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.audit_preview_label = ctk.CTkLabel(audit_frame, text="No images uploaded yet.", font=ctk.CTkFont(size=14), wraplength=400, justify="left", text_color="#D1D5DB")
        self.audit_preview_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        recommendations_frame = ctk.CTkFrame(audit_frame, corner_radius=10, fg_color="#2B2B2B")
        recommendations_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        recommendations_frame.grid_columnconfigure(0, weight=1)
        rec_label = ctk.CTkLabel(recommendations_frame, text="AI Recommendations", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF")
        rec_label.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")
        self.audit_rec_detail = ctk.CTkLabel(recommendations_frame, text="Upload product images to get suggestions.", font=ctk.CTkFont(size=12), text_color="#D1D5DB", wraplength=400, justify="left")
        self.audit_rec_detail.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

    def upload_audit_images(self):
        if not self.is_running:
            return
        file_paths = filedialog.askopenfilenames(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if not file_paths:
            return
        file_names = [os.path.basename(p) for p in file_paths]
        self.audit_preview_label.configure(text=f"Selected {len(file_names)} images:\n" + "\n".join(file_names))
        self.set_status("Analyzing products...", "blue")
        threading.Thread(target=self.process_audit_images, args=(file_paths,)).start()

    def process_audit_images(self, file_paths):
        if not self.is_running:
            return
        try:
            combined_text = ""
            for path in file_paths:
                img = Image.open(path)
                extracted = pytesseract.image_to_string(img)
                combined_text += extracted + "\n"
            analysis = self.analyze_audit_products(combined_text)
            if self.is_running:
                self.after(0, self.update_audit_recommendations, analysis)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error during audit: {e}", "red")

    def analyze_audit_products(self, text):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            You are an advanced Health Product Analysis AI. Analyze the following text from product images:
            {text}
            Respond in JSON format:
            ```json
            {
                "flagged": ["string"],
                "recommendations": ["string"]
            }
            ```
            """
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_text)
        except Exception as e:
            return {
                "flagged": ["High-sodium sauce"],
                "recommendations": ["Low-sodium soy sauce", "Olive oil spray"]
            }

    def update_audit_recommendations(self, analysis):
        if not self.is_running:
            return
        try:
            flagged_items = "\n".join(f"⚠️ {item}" for item in analysis.get("flagged", []))
            rec_items = "\n".join(f"✅ {item}" for item in analysis.get("recommendations", []))
            final_text = f"Flagged items:\n{flagged_items}\n\nRecommended alternatives:\n{rec_items}"
            self.audit_rec_detail.configure(text=final_text)
            self.set_status("Audit analysis complete.", "green")
        except Exception as e:
            self.audit_rec_detail.configure(text=f"Error displaying results: {e}")
            self.set_status("Error in audit display.", "red")

    # ===================================================================
    # TAB 6: AI Coach
    # ===================================================================
    def create_coach_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.coach_textbox = ctk.CTkTextbox(tab, corner_radius=10, state="disabled", font=("Arial", 14), wrap="word", fg_color="#2B2B2B", text_color="#FFFFFF")
        self.coach_textbox.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20,10))
        input_frame = ctk.CTkFrame(tab, fg_color="transparent")
        input_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Ask your AI coach a question...")
        self.chat_entry.grid(row=0, column=0, sticky="ew")
        self.chat_entry.bind("<Return>", self.send_chat_message)
        self.send_button = ctk.CTkButton(input_frame, text="Send", width=100, command=self.send_chat_message, fg_color="#3B82F6", hover_color="#60A5FA")
        self.send_button.grid(row=0, column=1, padx=(10, 0))
        # Mic Button for STT
        self.mic_button = ctk.CTkButton(input_frame, text="🎤 Speak", width=80,
            command=self.capture_voice_input, fg_color="#10B981", hover_color="#34D399")
        self.mic_button.grid(row=0, column=2, padx=(10, 0))

        # Speaker Button for TTS (replay last AI response)
        self.speaker_button = ctk.CTkButton(input_frame, text="🔊 Play", width=80,
        command=self.play_last_ai_response, fg_color="#F59E0B", hover_color="#FBBF24")
        self.speaker_button.grid(row=0, column=3, padx=(10, 0))

        self.update_chat_display("AI Coach: ", "Hello! I am your AI Health Coach. How can I help you today?", is_ai=True)

    def send_chat_message(self, event=None):
        if not self.is_running:
            return
        user_message = self.chat_entry.get()
        if not user_message.strip():
            return
        self.update_chat_display("You: ", user_message)
        self.chat_entry.delete(0, "end")
        self.chat_entry.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.set_status("AI Coach is thinking...", "blue")
        coach_thread = threading.Thread(target=self.run_coach_in_thread, args=(user_message,))
        coach_thread.start()

    def run_coach_in_thread(self, user_message):
        if not self.is_running:
            return
        try:
            response_text = self.get_gemini_coach_response(user_message)
            if self.is_running:
                self.after(0, self.update_chat_display, "AI Coach: ", response_text, True)
        except Exception as e:
            if self.is_running:
                self.after(0, self.update_chat_display, "AI Coach: ", f"Sorry, I encountered an error. Please try again. ({e})", True)
        finally:
            if self.is_running:
                self.after(0, self.enable_chat_input)

    def get_gemini_coach_response(self, user_message: str):
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are a friendly, encouraging, and knowledgeable AI Health Coach for the NutriScanAI app.
        You confidently give safe over-the-counter product suggestions, nutrition tips, and general wellness advice.
        You CAN suggest vitamins, supplements, skin-care products, diet plans, or lifestyle tips, as long as they are safe and commonly available.
        Only advise to see a doctor if the question clearly involves a medical emergency or serious illness.
        Keep answers:
        - Clear and concise (2–5 sentences),
        - Practical with examples (like specific nutrients or product types),
        - Friendly and helpful.
        User's question: "{user_message}"
        """
        response = model.generate_content(prompt)
        return response.text
    
    

    def update_chat_display(self, prefix, message, is_ai=False):
        if not self.is_running:
            return
        self.coach_textbox.configure(state="normal")
        tag_name = "ai_message" if is_ai else "user_message"
        self.coach_textbox.tag_config(tag_name, foreground="#3b82f6" if is_ai else "white")
        self.coach_textbox.insert("end", prefix, (tag_name,))
        self.coach_textbox.insert("end", message + "\n\n")
        self.coach_textbox.configure(state="disabled")
        self.coach_textbox.yview_moveto(1.0)

    def enable_chat_input(self):
        if not self.is_running:
            return
        self.chat_entry.configure(state="normal")
        self.send_button.configure(state="normal")
        self.set_status("Ready", "default")
        self.select_button.configure(state="normal")
        self.chat_entry.delete(0, "end")

    # ===================================================================
    # TAB 7: Subscriptions
    # ===================================================================
    def create_subscriptions_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure((0, 1, 2), weight=1)
        tab.grid_rowconfigure(0, weight=1)
        plans = {
            "Free": {"price": "$0/year", "features": ["Basic product scanning", "General health scores"], "color": "gray"},
            "Pro": {"price": "$99.99/year", "features": ["Tailored recommendations", "Daily tracking", "Full ingredient transparency"], "color": "#3b82f6"},
            "Elite": {"price": "$199.99/year", "features": ["All Pro features", "Genetic health integration", "AI health coaching"], "color": "gold"}
        }
        for i, (name, details) in enumerate(plans.items()):
            plan_frame = ctk.CTkFrame(tab, border_width=2, corner_radius=10, border_color=details["color"], fg_color="#2D3748")
            plan_frame.grid(row=0, column=i, padx=20, pady=20, sticky="nsew")
            plan_frame.grid_rowconfigure(1, weight=1)
            plan_header_frame = ctk.CTkFrame(plan_frame, fg_color="transparent")
            plan_header_frame.pack(pady=15, padx=20, fill="x")
            plan_name = ctk.CTkLabel(plan_header_frame, text=name, font=ctk.CTkFont(size=20, weight="bold"), text_color=details["color"])
            plan_name.pack()
            plan_price = ctk.CTkLabel(plan_header_frame, text=details["price"], font=ctk.CTkFont(size=18), text_color="#FFFFFF")
            plan_price.pack(pady=5)
            features_frame = ctk.CTkFrame(plan_frame, fg_color="transparent")
            features_frame.pack(pady=5, padx=20, fill="both", expand=True)
            for feature in details["features"]:
                feature_label = ctk.CTkLabel(features_frame, text=f"✓ {feature}", anchor="w", wraplength=180, text_color="#D1D5DB")
                feature_label.pack(pady=5, padx=10, fill="x")
            button_text = "Current Plan" if name == "Free" else f"Upgrade to {name}"
            button_state = "disabled" if name == "Free" else "normal"
            button = ctk.CTkButton(plan_frame, text=button_text, state=button_state, height=40, fg_color="#3B82F6", hover_color="#60A5FA")
            button.pack(side="bottom", fill="x", padx=20, pady=20)


    # ===================================================================
    # ===================================================================
    # ===================================================================
    # TAB 6: AI Coach (Upgraded with Voice Agent and Fixes)
    # ===================================================================
    def create_coach_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(tab, fg_color="transparent")
        top_bar.grid(row=0, column=0, padx=20, pady=(10,0), sticky="ew")

        ctk.CTkLabel(top_bar, text="Select Agent:").pack(side="left", padx=(0,10))
        self.agent_selector = ctk.CTkOptionMenu(
            top_bar,
            values=list(self.agents.keys()),
            command=self.switch_agent
        )
        self.agent_selector.pack(side="left")

        self.coach_textbox = ctk.CTkTextbox(tab, corner_radius=10, state="disabled", font=("Arial", 14), wrap="word", fg_color="#2B2B2B", text_color="#FFFFFF")
        self.coach_textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(10,10))

        input_frame = ctk.CTkFrame(tab, fg_color="transparent")
        input_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        input_frame.grid_columnconfigure(0, weight=1)

        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Ask your AI coach a question...")
        self.chat_entry.grid(row=0, column=0, sticky="ew")
        self.chat_entry.bind("<Return>", self.send_chat_message)

        self.send_button = ctk.CTkButton(input_frame, text="Send", width=100, command=self.send_chat_message, fg_color="#3B82F6", hover_color="#60A5FA")
        self.send_button.grid(row=0, column=1, padx=(10, 0))

        self.mic_button = ctk.CTkButton(input_frame, text="🎤 Speak", width=80,
                                        command=self.capture_voice_input, fg_color="#10B981", hover_color="#34D399")
        self.mic_button.grid(row=0, column=2, padx=(10, 0))

        self.speaker_button = ctk.CTkButton(input_frame, text="🔊 Play", width=80,
                                            command=self.play_last_ai_response, fg_color="#F59E0B", hover_color="#FBBF24")
        self.speaker_button.grid(row=0, column=3, padx=(10, 0))

        # Add pause button for voice
        self.pause_button = ctk.CTkButton(
            input_frame,
            text="⏸️ Pause",
            width=80,
            command=self.pause_voice,
            fg_color="#EF4444",
            hover_color="#DC2626",
            state="disabled"
        )
        self.pause_button.grid(row=0, column=4, padx=(10, 0))

        # Initialize voice control variables
        self.is_speaking = False
        self.is_paused = False
        self.current_audio_process = None

        self.update_chat_display("AI Coach: ", "Hello! I am your AI Health Coach. How can I help you today?", is_ai=True)

    def switch_agent(self, selected_agent_name: str):
        self.current_agent = self.agents[selected_agent_name]
        self.set_status(f"Agent switched to {selected_agent_name}", "blue")
        self.update_chat_display("System: ", f"Switched to {selected_agent_name}. How can I help?", is_ai=True)

    def capture_voice_input(self):
        self.set_status("Listening...", "blue")
        self.mic_button.configure(state="disabled")
        threading.Thread(target=self._threaded_listen, daemon=True).start()

    def _threaded_listen(self):
        if not self.is_running: return
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                if self.is_running: self.after(0, self.process_transcribed_text, text)
            except sr.WaitTimeoutError:
                 if self.is_running: self.after(0, self.set_status, "Listening timed out. Please try again.", "red")
            except sr.UnknownValueError:
                 if self.is_running: self.after(0, self.set_status, "Sorry, I could not understand the audio.", "red")
            except sr.RequestError as e:
                 if self.is_running: self.after(0, self.set_status, f"STT service error; {e}", "red")
            finally:
                # ✅ BUG FIX: This lambda function correctly re-enables the button every time.
                if self.is_running: self.after(0, lambda: self.mic_button.configure(state="normal"))

    def process_transcribed_text(self, text):
        # ✅ NEW LOGIC: Remembers that the input was voice.
        self.last_input_was_voice = True 
        self.chat_entry.delete(0, "end")
        self.chat_entry.insert(0, text)
        self.set_status("Voice transcribed. Sending to AI...", "green")
        self.send_chat_message()

    def speak_response(self, text: str):
        if not text or not self.is_running: return
        self.is_speaking = True
        self.is_paused = False
        self.speaker_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="⏸️ Pause")
        threading.Thread(target=self._threaded_speak, args=(text,), daemon=True).start()

    def pause_voice(self):
        """Pause or resume voice playback"""
        if not self.is_speaking:
            return
            
        if self.is_paused:
            # Resume
            self.is_paused = False
            self.pause_button.configure(text="⏸️ Pause")
            self.set_status("Voice resumed", "blue")
        else:
            # Pause
            self.is_paused = True
            self.pause_button.configure(text="▶️ Resume")
            self.set_status("Voice paused", "orange")
            
        # Note: Actual pause/resume would require more complex audio handling
        # This is a simplified implementation

    def stop_voice_on_tab_change(self):
        """Stop voice when changing tabs"""
        if self.is_speaking:
            self.is_speaking = False
            self.is_paused = False
            self.pause_button.configure(state="disabled", text="⏸️ Pause")
            self.speaker_button.configure(state="normal")
            self.set_status("Voice stopped", "blue")

    def _threaded_speak(self, text: str):
        try:
            tts = gTTS(text=text, lang='en')
            temp_file = "temp_response.mp3"
            tts.save(temp_file)
            
            # Check if speaking was stopped before playing
            if not self.is_speaking:
                return
                
            playsound(temp_file)
            os.remove(temp_file)
        except Exception as e:
            print(f"TTS Error: {e}")
            if self.is_running: self.after(0, self.set_status, "Error playing audio.", "red")
        finally:
            if self.is_running:
                self.after(0, lambda: self.speaker_button.configure(state="normal"))
                self.after(0, lambda: self.pause_button.configure(state="disabled", text="⏸️ Pause"))
                self.is_speaking = False
                self.is_paused = False

    def play_last_ai_response(self):
        if self.last_ai_response:
            self.set_status("Replaying last response...", "blue")
            self.speak_response(self.last_ai_response)
        else:
            self.set_status("No response to play yet.", "red")

    def send_chat_message(self, event=None):
        # If this function is called directly (not from voice), we set the flag to False.
        # But if it was called from voice, the flag is already True, so we check.
        if not hasattr(self, 'last_input_was_voice') or not self.last_input_was_voice:
             self.last_input_was_voice = False
             
        if not self.is_running: return
        user_message = self.chat_entry.get()
        if not user_message.strip(): return
        
        self.update_chat_display("You: ", user_message)
        self.chat_entry.delete(0, "end")
        self.chat_entry.configure(state="disabled")
        self.send_button.configure(state="disabled")
        self.set_status("AI Coach is thinking...", "blue")
        
        coach_thread = threading.Thread(target=self.run_coach_in_thread, args=(user_message,))
        coach_thread.start()
        
        # Reset the flag after sending the message
        self.last_input_was_voice = False

    def run_coach_in_thread(self, user_message):
        if not self.is_running: return
        try:
            response_text = self.current_agent.get_response(user_message, self.profile_data)
            self.last_ai_response = response_text
            if self.is_running:
                self.after(0, self.update_chat_display, "AI Coach: ", response_text, True)
                
                # ✅ NEW LOGIC: Only speak if the last input was from voice.
                if self.last_input_was_voice:
                    self.speak_response(response_text)
        except Exception as e:
            error_message = f"Sorry, I encountered an error. Please try again. ({e})"
            self.last_ai_response = error_message
            if self.is_running:
                self.after(0, self.update_chat_display, "AI Coach: ", error_message, True)
        finally:
            if self.is_running:
                self.after(0, self.enable_chat_input)

    def update_chat_display(self, prefix, message, is_ai=False):
        if not self.is_running: return
        self.coach_textbox.configure(state="normal")
        tag_name = "ai_message" if is_ai else "user_message"
        self.coach_textbox.tag_config(tag_name, foreground="#3b82f6" if is_ai else "white")
        self.coach_textbox.insert("end", prefix, (tag_name,))
        self.coach_textbox.insert("end", message + "\n\n")
        self.coach_textbox.configure(state="disabled")
        self.coach_textbox.yview_moveto(1.0)

    def enable_chat_input(self):
        if not self.is_running: return
        self.chat_entry.configure(state="normal")
        self.send_button.configure(state="normal")
        self.set_status("Ready", "default")
        try:
            self.select_button.configure(state="normal")
        except AttributeError:
            pass
        self.chat_entry.delete(0, "end")
    # ===================================================================
    # TAB 7: Subscriptions
    # ===================================================================
    def create_subscriptions_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure((0, 1, 2), weight=1)
        tab.grid_rowconfigure(0, weight=1)
        plans = {
            "Free": {"price": "$0/year", "features": ["Basic product scanning", "General health scores"], "color": "gray"},
            "Pro": {"price": "$99.99/year", "features": ["Tailored recommendations", "Daily tracking", "Full ingredient transparency"], "color": "#3b82f6"},
            "Elite": {"price": "$199.99/year", "features": ["All Pro features", "Genetic health integration", "AI health coaching"], "color": "gold"}
        }
        for i, (name, details) in enumerate(plans.items()):
            plan_frame = ctk.CTkFrame(tab, border_width=2, corner_radius=10, border_color=details["color"], fg_color="#2D3748")
            plan_frame.grid(row=0, column=i, padx=20, pady=20, sticky="nsew")
            plan_frame.grid_rowconfigure(1, weight=1)
            plan_header_frame = ctk.CTkFrame(plan_frame, fg_color="transparent")
            plan_header_frame.pack(pady=15, padx=20, fill="x")
            plan_name = ctk.CTkLabel(plan_header_frame, text=name, font=ctk.CTkFont(size=20, weight="bold"), text_color=details["color"])
            plan_name.pack()
            plan_price = ctk.CTkLabel(plan_header_frame, text=details["price"], font=ctk.CTkFont(size=18), text_color="#FFFFFF")
            plan_price.pack(pady=5)
            features_frame = ctk.CTkFrame(plan_frame, fg_color="transparent")
            features_frame.pack(pady=5, padx=20, fill="both", expand=True)
            for feature in details["features"]:
                feature_label = ctk.CTkLabel(features_frame, text=f"✓ {feature}", anchor="w", wraplength=180, text_color="#D1D5DB")
                feature_label.pack(pady=5, padx=10, fill="x")
            button_text = "Current Plan" if name == "Free" else f"Upgrade to {name}"
            button_state = "disabled" if name == "Free" else "normal"
            button = ctk.CTkButton(plan_frame, text=button_text, state=button_state, height=40, fg_color="#3B82F6", hover_color="#60A5FA")
            button.pack(side="bottom", fill="x", padx=20, pady=20)

    # ===================================================================
    # TAB 8: Meal Planner
    # ===================================================================
    def create_meal_planner_tab(self, tab):
        if not self.is_running:
            return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        title_label = ctk.CTkLabel(
            tab,
            text="Meal Planner",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFFFFF"
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Options frame for veg/nonveg and other preferences
        options_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2B2B2B")
        options_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        options_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Dietary preference
        ctk.CTkLabel(options_frame, text="Dietary Preference:", font=ctk.CTkFont(weight="bold"), text_color="#FFFFFF").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.dietary_preference = ctk.CTkOptionMenu(
            options_frame,
            values=["Vegetarian", "Non-Vegetarian", "Vegan", "Flexitarian"],
            command=self.on_dietary_change
        )
        self.dietary_preference.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Calorie target
        ctk.CTkLabel(options_frame, text="Daily Calories:", font=ctk.CTkFont(weight="bold"), text_color="#FFFFFF").grid(row=0, column=2, padx=10, pady=10, sticky="w")
        self.calorie_target = ctk.CTkOptionMenu(
            options_frame,
            values=["1200-1500", "1500-1800", "1800-2100", "2100-2400", "2400+"],
            command=self.on_calorie_change
        )
        self.calorie_target.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

        # Generate button
        generate_button = ctk.CTkButton(
            tab,
            text="Generate Weekly Meal Plan",
            command=self.generate_meal_plan,
            height=40,
            fg_color="#3B82F6",
            hover_color="#60A5FA"
        )
        generate_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # Meal plan display with edit capabilities
        meal_plan_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2B2B2B")
        meal_plan_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        meal_plan_frame.grid_columnconfigure(0, weight=1)
        meal_plan_frame.grid_rowconfigure(1, weight=1)

        meal_plan_header = ctk.CTkFrame(meal_plan_frame, fg_color="transparent")
        meal_plan_header.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        meal_plan_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(meal_plan_header, text="Weekly Meal Plan", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF").grid(row=0, column=0, sticky="w")
        self.edit_meal_plan_button = ctk.CTkButton(
            meal_plan_header,
            text="Edit Plan",
            command=self.toggle_meal_plan_editing,
            width=100,
            height=30,
            fg_color="#10B981",
            hover_color="#059669"
        )
        self.edit_meal_plan_button.grid(row=0, column=1, padx=(10, 0))

        self.meal_plan_textbox = ctk.CTkTextbox(
            meal_plan_frame,
            corner_radius=10,
            state="disabled",
            font=("Arial", 14),
            wrap="word",
            fg_color="#2B2B2B",
            text_color="#FFFFFF"
        )
        self.meal_plan_textbox.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # Shopping list section
        shopping_list_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2B2B2B")
        shopping_list_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        shopping_list_frame.grid_columnconfigure(0, weight=1)

        shopping_list_header = ctk.CTkFrame(shopping_list_frame, fg_color="transparent")
        shopping_list_header.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        shopping_list_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(shopping_list_header, text="Shopping List", font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF").grid(row=0, column=0, sticky="w")
        self.generate_shopping_list_button = ctk.CTkButton(
            shopping_list_header,
            text="Generate List",
            command=self.generate_shopping_list,
            width=120,
            height=30,
            fg_color="#F59E0B",
            hover_color="#D97706"
        )
        self.generate_shopping_list_button.grid(row=0, column=1, padx=(10, 0))

        self.shopping_list_textbox = ctk.CTkTextbox(
            shopping_list_frame,
            corner_radius=10,
            state="disabled",
            font=("Arial", 12),
            wrap="word",
            fg_color="#2B2B2B",
            text_color="#D1D5DB",
            height=120
        )
        self.shopping_list_textbox.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")

        # Initialize meal plan data
        self.current_meal_plan = None
        self.meal_plan_editable = False

    def on_dietary_change(self, value):
        # Add any additional logic you want to execute when dietary preference changes
        print(f"Dietary preference changed: {value}")

    def on_calorie_change(self, value):
        # Add any additional logic you want to execute when calorie target changes
        print(f"Calorie target changed: {value}")

    def generate_meal_plan(self):
        # Add logic to generate a meal plan based on the selected dietary preference and calorie target
        print("Generating meal plan...")
        # You might want to call a function to fetch recipes based on these preferences
        self.set_status("Meal plan generation in progress...", "blue")
        threading.Thread(target=self.fetch_and_display_meal_plan).start()

    def fetch_and_display_meal_plan(self):
        if not self.is_running:
            return
        try:
            meal_plan_data = self.get_meal_plan()
            if self.is_running:
                self.after(0, self.display_meal_plan, meal_plan_data)
        except Exception as e:
            if self.is_running:
                self.after(0, self.set_status, f"Error generating meal plan: {e}", "red")

    def get_meal_plan(self):
        model = genai.GenerativeModel('gemini-1.5-flash')
        allergies = self.profile_data.get("allergies", "")
        goals = self.profile_data.get("goals", "")
        scanned_foods = json.dumps(self.scanned_foods)
        dietary_pref = self.dietary_preference.get()
        calorie_target = self.calorie_target.get()

        json_template = """
{
  "meal_plan": [
    {
      "day": "string",
      "meals": {
        "breakfast": {"name": "string", "ingredients": ["string"], "calories": "string", "prep_time": "string"},
        "lunch": {"name": "string", "ingredients": ["string"], "calories": "string", "prep_time": "string"},
        "dinner": {"name": "string", "ingredients": ["string"], "calories": "string", "prep_time": "string"}
      }
    }
  ],
  "shopping_list": ["string"],
  "total_weekly_calories": "string"
}
"""
        prompt = (
            f"You are a nutritionist AI for NutriScanAI. Generate a personalized 7-day meal plan based on the user's preferences:\n"
            f"- Dietary Preference: {dietary_pref}\n"
            f"- Daily Calorie Target: {calorie_target}\n"
            f"- Allergies: {allergies}\n"
            f"- Health Goals: {goals}\n"
            f"- Scanned Foods Available: {scanned_foods}\n\n"
            f"Requirements:\n"
            f"1. Create 7 days of meals (breakfast, lunch, dinner)\n"
            f"2. Respect the dietary preference strictly\n"
            f"3. Stay within the calorie target range\n"
            f"4. Avoid any allergens\n"
            f"5. Include preparation time for each meal\n"
            f"6. Use scanned foods where possible\n"
            f"7. Provide a comprehensive shopping list\n\n"
            f"Respond in JSON format:\n"
            f"```json\n{json_template}\n```\n"
        )
        try:
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(json_text)
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            # Return fallback meal plan based on dietary preference
            return self.get_fallback_meal_plan(dietary_pref, calorie_target)

    def get_fallback_meal_plan(self, dietary_pref, calorie_target):
        """Fallback meal plans for different dietary preferences"""
        vegetarian_plan = {
            "meal_plan": [
                {
                    "day": "Monday",
                    "meals": {
                        "breakfast": {"name": "Oatmeal with Berries", "ingredients": ["oats", "milk", "blueberries", "honey"], "calories": "350 kcal", "prep_time": "10 min"},
                        "lunch": {"name": "Quinoa Buddha Bowl", "ingredients": ["quinoa", "chickpeas", "spinach", "tomato", "cucumber"], "calories": "450 kcal", "prep_time": "20 min"},
                        "dinner": {"name": "Lentil Curry", "ingredients": ["lentils", "onion", "tomato", "garlic", "rice"], "calories": "400 kcal", "prep_time": "25 min"}
                    }
                },
                {
                    "day": "Tuesday",
                    "meals": {
                        "breakfast": {"name": "Greek Yogurt Parfait", "ingredients": ["greek yogurt", "granola", "strawberries", "honey"], "calories": "320 kcal", "prep_time": "5 min"},
                        "lunch": {"name": "Mediterranean Salad", "ingredients": ["mixed greens", "feta cheese", "olives", "cucumber", "olive oil"], "calories": "380 kcal", "prep_time": "15 min"},
                        "dinner": {"name": "Vegetable Stir Fry", "ingredients": ["tofu", "broccoli", "carrots", "soy sauce", "brown rice"], "calories": "420 kcal", "prep_time": "20 min"}
                    }
                }
            ],
            "shopping_list": ["oats", "milk", "blueberries", "honey", "quinoa", "chickpeas", "spinach", "tomato", "cucumber", "lentils", "onion", "garlic", "rice", "greek yogurt", "granola", "strawberries", "mixed greens", "feta cheese", "olives", "olive oil", "tofu", "broccoli", "carrots", "soy sauce", "brown rice"],
            "total_weekly_calories": "1750 kcal"
        }
        
        non_vegetarian_plan = {
            "meal_plan": [
                {
                    "day": "Monday",
                    "meals": {
                        "breakfast": {"name": "Eggs and Toast", "ingredients": ["eggs", "whole grain bread", "butter", "salt"], "calories": "380 kcal", "prep_time": "10 min"},
                        "lunch": {"name": "Grilled Chicken Salad", "ingredients": ["chicken breast", "lettuce", "tomato", "cucumber", "olive oil"], "calories": "420 kcal", "prep_time": "15 min"},
                        "dinner": {"name": "Baked Salmon", "ingredients": ["salmon", "quinoa", "spinach", "lemon"], "calories": "450 kcal", "prep_time": "25 min"}
                    }
                },
                {
                    "day": "Tuesday",
                    "meals": {
                        "breakfast": {"name": "Protein Smoothie", "ingredients": ["banana", "protein powder", "milk", "peanut butter"], "calories": "350 kcal", "prep_time": "5 min"},
                        "lunch": {"name": "Turkey Sandwich", "ingredients": ["turkey", "whole grain bread", "lettuce", "tomato", "mayo"], "calories": "400 kcal", "prep_time": "10 min"},
                        "dinner": {"name": "Beef Stir Fry", "ingredients": ["beef strips", "broccoli", "carrots", "soy sauce", "brown rice"], "calories": "480 kcal", "prep_time": "20 min"}
                    }
                }
            ],
            "shopping_list": ["eggs", "whole grain bread", "butter", "salt", "chicken breast", "lettuce", "tomato", "cucumber", "olive oil", "salmon", "quinoa", "spinach", "lemon", "banana", "protein powder", "milk", "peanut butter", "turkey", "mayo", "beef strips", "broccoli", "carrots", "soy sauce", "brown rice"],
            "total_weekly_calories": "1850 kcal"
        }
        
        if dietary_pref == "Vegetarian":
            return vegetarian_plan
        elif dietary_pref == "Non-Vegetarian":
            return non_vegetarian_plan
        else:
            return vegetarian_plan  # Default to vegetarian

    def display_meal_plan(self, meal_plan_data):
        if not self.is_running:
            return
            
        self.current_meal_plan = meal_plan_data
        self.meal_plan_textbox.configure(state="normal")
        self.meal_plan_textbox.delete("1.0", "end")
        
        # Display dietary info
        dietary_pref = self.dietary_preference.get()
        calorie_target = self.calorie_target.get()
        self.meal_plan_textbox.insert("end", f"🍽️ {dietary_pref} Meal Plan - {calorie_target} calories/day\n", "header")
        self.meal_plan_textbox.insert("end", "=" * 50 + "\n\n")
        
        for day_plan in meal_plan_data.get("meal_plan", []):
            self.meal_plan_textbox.insert("end", f"📅 {day_plan['day']}:\n", "day_header")
            for meal_type, meal in day_plan["meals"].items():
                self.meal_plan_textbox.insert("end", f"  🍳 {meal_type.capitalize()}: {meal['name']}\n", "meal_name")
                self.meal_plan_textbox.insert("end", f"     ⏰ Prep Time: {meal['prep_time']} | 🔥 Calories: {meal['calories']}\n", "meal_details")
                self.meal_plan_textbox.insert("end", f"     📝 Ingredients: {', '.join(meal['ingredients'])}\n\n", "ingredients")
        
        # Display total calories
        total_calories = meal_plan_data.get("total_weekly_calories", "N/A")
        self.meal_plan_textbox.insert("end", f"📊 Total Weekly Calories: {total_calories}\n", "total_calories")
        
        # Configure text tags for styling
        self.meal_plan_textbox.tag_config("header", font=ctk.CTkFont(size=16, weight="bold"), foreground="#3B82F6")
        self.meal_plan_textbox.tag_config("day_header", font=ctk.CTkFont(size=14, weight="bold"), foreground="#10B981")
        self.meal_plan_textbox.tag_config("meal_name", font=ctk.CTkFont(weight="bold"), foreground="#FFFFFF")
        self.meal_plan_textbox.tag_config("meal_details", foreground="#F59E0B")
        self.meal_plan_textbox.tag_config("ingredients", foreground="#D1D5DB")
        self.meal_plan_textbox.tag_config("total_calories", font=ctk.CTkFont(weight="bold"), foreground="#EF4444")
        
        self.meal_plan_textbox.configure(state="disabled")
        self.set_status("Meal plan generated successfully!", "green")

    def toggle_meal_plan_editing(self):
        self.meal_plan_editable = not self.meal_plan_editable
        if self.meal_plan_editable:
            self.edit_meal_plan_button.configure(text="Save Plan")
            self.meal_plan_textbox.configure(state="normal")
        else:
            self.edit_meal_plan_button.configure(text="Edit Plan")
            self.meal_plan_textbox.configure(state="disabled")

    def generate_shopping_list(self):
        # Add logic to generate a shopping list based on the current meal plan
        print("Generating shopping list...")
        self.set_status("Shopping list generation in progress...", "blue")
        threading.Thread(target=self.fetch_and_display_shopping_list).start()

    def fetch_and_display_shopping_list(self):
        if not self.is_running:
            return
            
        if not self.current_meal_plan:
            self.set_status("Please generate a meal plan first!", "red")
            return
            
        try:
            # Extract shopping list from current meal plan
            shopping_list = self.current_meal_plan.get("shopping_list", [])
            
            # Organize by categories
            categorized_list = self.categorize_shopping_list(shopping_list)
            
            self.shopping_list_textbox.configure(state="normal")
            self.shopping_list_textbox.delete("1.0", "end")
            
            # Display categorized shopping list
            self.shopping_list_textbox.insert("end", "🛒 Shopping List\n", "header")
            self.shopping_list_textbox.insert("end", "=" * 30 + "\n\n", "header")
            
            for category, items in categorized_list.items():
                self.shopping_list_textbox.insert("end", f"📦 {category}:\n", "category")
                for item in items:
                    self.shopping_list_textbox.insert("end", f"  • {item}\n", "item")
                self.shopping_list_textbox.insert("end", "\n")
            
            # Configure text tags for styling
            self.shopping_list_textbox.tag_config("header", font=ctk.CTkFont(size=14, weight="bold"), foreground="#3B82F6")
            self.shopping_list_textbox.tag_config("category", font=ctk.CTkFont(weight="bold"), foreground="#10B981")
            self.shopping_list_textbox.tag_config("item", foreground="#D1D5DB")
            
            self.shopping_list_textbox.configure(state="disabled")
            self.set_status("Shopping list generated successfully!", "green")
            
        except Exception as e:
            self.set_status(f"Error generating shopping list: {e}", "red")

    def categorize_shopping_list(self, items):
        """Categorize shopping list items for better organization"""
        categories = {
            "Proteins": [],
            "Vegetables": [],
            "Fruits": [],
            "Grains": [],
            "Dairy": [],
            "Pantry": [],
            "Spices & Condiments": []
        }
        
        # Define item categories
        protein_items = ["chicken", "beef", "pork", "fish", "salmon", "tuna", "eggs", "tofu", "lentils", "chickpeas", "turkey"]
        vegetable_items = ["spinach", "lettuce", "tomato", "cucumber", "broccoli", "carrots", "onion", "garlic", "bell pepper", "mushrooms"]
        fruit_items = ["apple", "banana", "orange", "strawberries", "blueberries", "grapes", "mango", "pineapple"]
        grain_items = ["rice", "quinoa", "oats", "bread", "pasta", "flour", "cereal"]
        dairy_items = ["milk", "cheese", "yogurt", "butter", "cream"]
        pantry_items = ["oil", "sugar", "salt", "pepper", "vinegar", "sauce"]
        spice_items = ["cumin", "turmeric", "paprika", "oregano", "basil", "thyme", "cinnamon", "nutmeg"]
        
        for item in items:
            item_lower = item.lower()
            if any(protein in item_lower for protein in protein_items):
                categories["Proteins"].append(item)
            elif any(veg in item_lower for veg in vegetable_items):
                categories["Vegetables"].append(item)
            elif any(fruit in item_lower for fruit in fruit_items):
                categories["Fruits"].append(item)
            elif any(grain in item_lower for grain in grain_items):
                categories["Grains"].append(item)
            elif any(dairy in item_lower for dairy in dairy_items):
                categories["Dairy"].append(item)
            elif any(spice in item_lower for spice in spice_items):
                categories["Spices & Condiments"].append(item)
            elif any(pantry in item_lower for pantry in pantry_items):
                categories["Pantry"].append(item)
            else:
                categories["Pantry"].append(item)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    # ===================================================================
    # ✨ NEW: Helper methods for Family Hub photos
    # ===================================================================
    def setup_member_photos(self):
        """Creates placeholder images for family members if they don't exist."""
        photo_dir = "member_photos"
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)
            print(f"Created directory: {photo_dir}")

        members_to_create = {
            "sarah.png": "#e57373",
            "mike.png": "#64b5f6",
            "emma.png": "#ba68c8",
            "rose.png": "#ffd54f"
        }

        for filename, color in members_to_create.items():
            filepath = os.path.join(photo_dir, filename)
            if not os.path.exists(filepath):
                try:
                    img = Image.new('RGB', (100, 100), color=color)
                    img.save(filepath)
                    print(f"Created placeholder photo: {filepath}")
                except Exception as e:
                    print(f"Failed to create placeholder photo {filepath}: {e}")

    def create_circular_image(self, image_path, size):
        """Crops an image to a circle. Handles errors gracefully."""
        try:
            img = Image.open(image_path).convert("RGBA")
            img = img.resize(size, Image.Resampling.LANCZOS)

            # Create a circular mask
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)

            # Apply mask
            circular_img = Image.new("RGBA", size, (0, 0, 0, 0))
            circular_img.paste(img, (0, 0), mask)
            return circular_img
        except FileNotFoundError:
            # Return a plain grey circle if the image is not found
            print(f"Warning: Image not found at {image_path}. Creating fallback.")
            fallback = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(fallback)
            draw.ellipse((0, 0) + size, fill='#555555')
            return fallback
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            return None

    # ===================================================================
    # TAB 9: Family Hub (UPDATED with Photos)
    # ===================================================================
    def create_family_hub_tab(self, tab):
        if not self.is_running:
            return

        # Mock data based on the provided PDF
        family_data = [
            {"name": "Sarah Johnson", "photo": "sarah.png", "role": "Mother", "age": 42, "status": "Good", "steps": "8,420", "last_meal": "2 hours ago", "status_color": "#22C55E"},
            {"name": "Mike Johnson", "photo": "mike.png", "role": "Father", "age": 45, "status": "Excellent", "steps": "12,050", "last_meal": "3 hours ago", "status_color": "#3B82F6"},
            {"name": "Emma Johnson", "photo": "emma.png", "role": "Daughter", "age": 16, "status": "Good", "steps": "6,200", "last_meal": "1 hour ago", "status_color": "#22C55E"},
            {"name": "Grandma Rose", "photo": "rose.png", "role": "Grandmother", "age": 68, "status": "Warning", "steps": "3,200", "last_meal": "5 hours ago", "status_color": "#FBBF24"},
        ]

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # --- Main Header ---
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        title_label = ctk.CTkLabel(header_frame, text="Family Health Hub", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        add_member_button = ctk.CTkButton(header_frame, text="+ Add Member", fg_color="#3B82F6", hover_color="#60A5FA", command=lambda: self.set_status("Add Member functionality not implemented.", "blue"))
        add_member_button.grid(row=0, column=2, sticky="e")

        # --- Stats Bar ---
        stats_frame = ctk.CTkFrame(tab)
        stats_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def create_stat_card(parent, title, value):
            card = ctk.CTkFrame(parent, fg_color="transparent")
            value_label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold"))
            value_label.pack()
            title_label = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12), text_color="gray")
            title_label.pack()
            return card

        create_stat_card(stats_frame, "Family Members", "4").grid(row=0, column=0, pady=10)
        create_stat_card(stats_frame, "Active Today", "3").grid(row=0, column=1, pady=10)
        create_stat_card(stats_frame, "Pending Alerts", "3").grid(row=0, column=2, pady=10)
        
        # Family Goal Progress
        goal_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        goal_frame.grid(row=0, column=3, pady=10, padx=10, sticky="ew")
        goal_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(goal_frame, text="Family Goal", font=ctk.CTkFont(size=12), text_color="gray").grid(row=0, column=0, sticky="w")
        progress_bar = ctk.CTkProgressBar(goal_frame, progress_color="#22C55E")
        progress_bar.set(0.85)
        progress_bar.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(goal_frame, text="85%", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, padx=(10, 0))

        # --- Members Scrollable Frame ---
        scroll_frame = ctk.CTkScrollableFrame(tab)
        scroll_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=1)

        for i, member in enumerate(family_data):
            card = ctk.CTkFrame(scroll_frame, corner_radius=10, fg_color="#2D3748")
            card.grid(row=i, column=0, padx=10, pady=10, sticky="ew")
            card.grid_columnconfigure(1, weight=1)
            
            # ✨ UPDATED: Member Photo Icon
            photo_path = os.path.join("member_photos", member["photo"])
            circular_photo = self.create_circular_image(photo_path, (60, 60))
            if circular_photo:
                ctk_photo = ctk.CTkImage(light_image=circular_photo, dark_image=circular_photo, size=(60, 60))
                photo_label = ctk.CTkLabel(card, image=ctk_photo, text="")
                photo_label.grid(row=0, column=0, rowspan=2, padx=15, pady=15, sticky="ns")

            # Member Info
            name_label = ctk.CTkLabel(card, text=member["name"], font=ctk.CTkFont(size=16, weight="bold"), anchor="w")
            name_label.grid(row=0, column=1, sticky="sw", padx=10)
            role_label = ctk.CTkLabel(card, text=f"{member['role']} {member['age']} years", text_color="gray", anchor="w")
            role_label.grid(row=1, column=1, sticky="nw", padx=10)

            # Status Button
            status_button = ctk.CTkButton(card, text=member["status"], fg_color=member["status_color"], hover=False, state="disabled", width=80)
            status_button.grid(row=0, column=2, rowspan=2, padx=10)

            # Metrics
            steps_label = ctk.CTkLabel(card, text=f"Daily Steps: {member['steps']}", anchor="w")
            steps_label.grid(row=0, column=3, padx=20)
            meal_label = ctk.CTkLabel(card, text=f"Last Meal: {member['last_meal']}", anchor="w")
            meal_label.grid(row=1, column=3, padx=20)
            
            # View Profile Button
            profile_button = ctk.CTkButton(card, text="View Profile", fg_color="transparent", border_width=1, border_color="#3B82F6", text_color="#3B82F6", hover_color="#1F2937", command=lambda name=member['name']: self.set_status(f"Viewing profile for {name}", "blue"))
            profile_button.grid(row=0, column=4, rowspan=2, padx=15)

        # --- Family Insights ---
        insights_frame = ctk.CTkFrame(tab, corner_radius=10)
        insights_frame.grid(row=3, column=0, padx=20, pady=20, sticky="ew")
        insights_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(insights_frame, text="Today's Family Insights", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")
        ctk.CTkLabel(insights_frame, text="• Great progress! Your family walked 29,870 steps today that's 15% above your combined goal.", wraplength=800, justify="left").grid(row=1, column=0, padx=20, pady=2, sticky="w")
        ctk.CTkLabel(insights_frame, text="• Nutrition reminder: Consider adding more calcium-rich foods to this week's meal plan.", wraplength=800, justify="left").grid(row=2, column=0, padx=20, pady=(2, 10), sticky="w")

    # ===================================================================
    # TAB 10: Pain Relief & Exercises (NEW FEATURE)
    # ===================================================================
    def create_pain_relief_tab(self, tab):
        """Creates the pain relief and exercise recommendation tab."""
        if not self.is_running:
            return
        
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        title_label = ctk.CTkLabel(header_frame, text="🩺 Pain Relief & Exercise Recommendations", 
                                  font=ctk.CTkFont(size=24, weight="bold"), text_color="#FFFFFF")
        title_label.pack(side="left")
        
        # Pain Input Section
        input_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2D3748")
        input_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)
        
        # Pain Type Selection
        ctk.CTkLabel(input_frame, text="Pain/Discomfort Type:", 
                    font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF").grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        
        # Common pain types dropdown
        common_pain_types = [
            "Back Pain", "Neck Pain", "Knee Pain", "Shoulder Pain", "Hip Pain",
            "Ankle Pain", "Wrist Pain", "Elbow Pain", "Headache", "Stress",
            "Joint Stiffness", "Muscle Tension", "Sciatica", "Arthritis", "Fibromyalgia"
        ]
        
        self.pain_type_var = ctk.StringVar(value="Select pain type...")
        self.pain_type_dropdown = ctk.CTkOptionMenu(
            input_frame, 
            values=common_pain_types,
            variable=self.pain_type_var,
            command=self.on_pain_type_selected
        )
        self.pain_type_dropdown.grid(row=0, column=1, padx=15, pady=(15, 5), sticky="ew")
        
        # Custom pain input
        ctk.CTkLabel(input_frame, text="Or describe your pain:", 
                    font=ctk.CTkFont(size=14), text_color="#D1D5DB").grid(row=1, column=0, padx=15, pady=(5, 5), sticky="w")
        
        self.custom_pain_entry = ctk.CTkEntry(
            input_frame, 
            placeholder_text="e.g., Lower back pain that worsens when sitting...",
            height=35
        )
        self.custom_pain_entry.grid(row=1, column=1, padx=15, pady=(5, 5), sticky="ew")
        
        # Get Recommendations Button
        self.get_recommendations_button = ctk.CTkButton(
            input_frame,
            text="Get Exercise Recommendations",
            command=self.get_exercise_recommendations,
            height=40,
            fg_color="#3B82F6",
            hover_color="#60A5FA"
        )
        self.get_recommendations_button.grid(row=2, column=0, columnspan=2, padx=15, pady=15, sticky="ew")
        
        # Results Section
        results_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2B2B2B")
        results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1)
        
        results_header = ctk.CTkLabel(
            results_frame, 
            text="AI-Generated Exercise Recommendations", 
            font=ctk.CTkFont(size=18, weight="bold"), 
            text_color="#FFFFFF"
        )
        results_header.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")
        
        # Scrollable results area
        self.results_scroll_frame = ctk.CTkScrollableFrame(results_frame, fg_color="transparent")
        self.results_scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="nsew")
        self.results_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Initial message
        self.initial_message = ctk.CTkLabel(
            self.results_scroll_frame,
            text="Select a pain type or describe your discomfort above, then click 'Get Exercise Recommendations' to receive personalized exercise and yoga suggestions.",
            font=ctk.CTkFont(size=14),
            text_color="#9CA3AF",
            wraplength=600,
            justify="center"
        )
        self.initial_message.pack(pady=50)
        
        # History Section
        history_frame = ctk.CTkFrame(tab, corner_radius=10, fg_color="#2D3748")
        history_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        history_frame.grid_columnconfigure(0, weight=1)
        
        history_header = ctk.CTkLabel(
            history_frame,
            text="📚 Exercise History",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        history_header.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        
        self.history_scroll_frame = ctk.CTkScrollableFrame(history_frame, height=120, fg_color="transparent")
        self.history_scroll_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.history_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Load exercise history
        self.load_exercise_history()

    def on_pain_type_selected(self, value):
        """Handle pain type selection from dropdown."""
        if value != "Select pain type...":
            self.custom_pain_entry.delete(0, "end")
            self.custom_pain_entry.insert(0, value)

    def get_exercise_recommendations(self):
        """Get AI-generated exercise recommendations for the specified pain/discomfort."""
        if not self.is_running:
            return
        
        # Get pain description
        pain_description = self.custom_pain_entry.get().strip()
        if not pain_description:
            self.set_status("Please describe your pain or select a pain type.", "red")
            return
        
        # Disable button and show loading
        self.get_recommendations_button.configure(state="disabled", text="Getting Recommendations...")
        self.set_status("Generating personalized exercise recommendations...", "blue")
        
        # Clear previous results
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()
        
        # Show loading indicator
        loading_label = ctk.CTkLabel(
            self.results_scroll_frame,
            text="🤖 AI is analyzing your pain and generating personalized exercise recommendations...",
            font=ctk.CTkFont(size=14),
            text_color="#9CA3AF"
        )
        loading_label.pack(pady=50)
        
        # Start AI analysis in thread
        threading.Thread(target=self.run_ai_exercise_analysis, args=(pain_description,), daemon=True).start()

    def run_ai_exercise_analysis(self, pain_description):
        """Run AI analysis in background thread."""
        if not self.is_running:
            return
        
        try:
            recommendations = self.get_ai_exercise_recommendations(pain_description)
            if self.is_running:
                self.after(0, self.display_exercise_recommendations, recommendations, pain_description)
        except Exception as e:
            error_msg = f"Error getting recommendations: {str(e)}"
            if self.is_running:
                self.after(0, self.display_exercise_error, error_msg)
        finally:
            if self.is_running:
                self.after(0, self.enable_recommendations_button)

    def get_ai_exercise_recommendations(self, pain_description):
        """Get exercise recommendations from Gemini API."""
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            You are an expert physical therapist and yoga instructor specializing in pain relief and rehabilitation.
            
            The user is experiencing: {pain_description}
            
            Provide 3-5 specific exercise or yoga recommendations that are:
            1. Safe and effective for their specific pain/discomfort
            2. Suitable for home practice
            3. Include both immediate relief and long-term rehabilitation exercises
            
            Respond ONLY with a valid JSON object in this exact format:
            {{
                "pain_area": "{pain_description}",
                "exercise_suggestions": [
                    {{
                        "name": "Exercise/Yoga Pose Name",
                        "description": "Detailed description of how to perform, benefits, and precautions",
                        "youtube_link": "https://www.youtube.com/watch?v=REAL_VIDEO_ID",
                        "difficulty": "Beginner/Intermediate/Advanced",
                        "duration": "Recommended duration (e.g., 5-10 minutes)",
                        "frequency": "How often to perform (e.g., 2-3 times daily)"
                    }}
                ],
                "notes": "General safety tips and when to consult a healthcare professional"
            }}
            
            IMPORTANT: For YouTube links, use REAL, POPULAR, and SPECIFIC exercise videos for the pain condition:
            - Back Pain: Use videos from channels like "AskDoctorJo", "Bob & Brad", "Physical Therapy Video"
            - Neck Pain: Use videos from "AskDoctorJo", "Bob & Brad", "Yoga With Adriene"
            - Knee Pain: Use videos from "AskDoctorJo", "Bob & Brad", "Knee Pain Explained"
            - Shoulder Pain: Use videos from "AskDoctorJo", "Bob & Brad", "Shoulder Pain Explained"
            - Stress/Anxiety: Use videos from "Yoga With Adriene", "Boho Beautiful Yoga", "Fightmaster Yoga"
            
            Search for videos with titles like:
            - "Best exercises for [specific pain] relief"
            - "[Pain type] exercises physical therapy"
            - "Yoga for [pain type] relief"
            - "Home exercises for [pain type]"
            
            Ensure all YouTube links are real, popular exercise videos with millions of views from reputable channels.
            Focus on evidence-based exercises that are commonly recommended by physical therapists.
            """
            
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            
            # Parse JSON response
            recommendations = json.loads(json_text)
            
            # Validate response structure
            required_fields = ["pain_area", "exercise_suggestions", "notes"]
            if not all(field in recommendations for field in required_fields):
                raise ValueError("Invalid response structure from AI")
            
            return recommendations
            
        except Exception as e:
            print(f"AI API Error: {e}")
            # Return fallback recommendations with realistic YouTube videos
            fallback_videos = {
                "back pain": [
                    "https://www.youtube.com/watch?v=2L916cqWXrI",  # AskDoctorJo - Back Pain Relief
                    "https://www.youtube.com/watch?v=9hVzXI1K8Q8"   # Bob & Brad - Lower Back Pain
                ],
                "neck pain": [
                    "https://www.youtube.com/watch?v=2NOsE-VPpkE",  # AskDoctorJo - Neck Pain Relief
                    "https://www.youtube.com/watch?v=QhHJC8scOLY"   # Bob & Brad - Neck Pain Relief
                ],
                "knee pain": [
                    "https://www.youtube.com/watch?v=Wvq7yqBdUcE",  # AskDoctorJo - Knee Pain Relief
                    "https://www.youtube.com/watch?v=1vuaaHosQvM"   # Bob & Brad - Knee Pain Relief
                ],
                "shoulder pain": [
                    "https://www.youtube.com/watch?v=3VcgVdEjC84",  # AskDoctorJo - Shoulder Pain Relief
                    "https://www.youtube.com/watch?v=3VcgVdEjC84"   # Bob & Brad - Shoulder Pain Relief
                ],
                "stress": [
                    "https://www.youtube.com/watch?v=inpok4MKVLM",  # Yoga With Adriene - Stress Relief
                    "https://www.youtube.com/watch?v=z6X5oEIg6Ak"   # Boho Beautiful - Stress Relief
                ]
            }
            
            # Find best matching fallback videos
            best_videos = []
            pain_lower = pain_description.lower()
            for pain_type, videos in fallback_videos.items():
                if pain_type in pain_lower:
                    best_videos = videos
                    break
            
            if not best_videos:
                best_videos = fallback_videos["back pain"]  # Default to back pain videos
            
            return {
                "pain_area": pain_description,
                "exercise_suggestions": [
                    {
                        "name": "Gentle Stretching & Mobility",
                        "description": "Start with gentle stretching exercises to improve flexibility and reduce pain. Move slowly and stop if you feel any sharp pain. Focus on controlled movements and deep breathing.",
                        "youtube_link": best_videos[0],
                        "difficulty": "Beginner",
                        "duration": "10-15 minutes",
                        "frequency": "2-3 times daily"
                    },
                    {
                        "name": "Deep Breathing & Relaxation",
                        "description": "Practice deep breathing exercises to relax muscles and reduce tension. Inhale deeply through your nose, hold for 4 seconds, exhale slowly. This helps reduce stress and muscle tension.",
                        "youtube_link": best_videos[1] if len(best_videos) > 1 else best_videos[0],
                        "difficulty": "Beginner",
                        "duration": "5-10 minutes",
                        "frequency": "As needed throughout the day"
                    }
                ],
                "notes": "These are general recommendations. If pain persists or worsens, please consult with a healthcare professional for personalized advice. The YouTube videos are from reputable physical therapy channels."
            }

    def display_exercise_recommendations(self, recommendations, pain_description):
        """Display the AI-generated exercise recommendations."""
        if not self.is_running:
            return
        
        # Clear loading indicator
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()
        
        # Display pain area
        pain_header = ctk.CTkLabel(
            self.results_scroll_frame,
            text=f"🎯 Recommendations for: {recommendations['pain_area']}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3B82F6"
        )
        pain_header.pack(pady=(0, 20))
        
        # Display each exercise recommendation
        for i, exercise in enumerate(recommendations['exercise_suggestions']):
            exercise_card = self.create_exercise_card(exercise, i + 1)
            exercise_card.pack(fill="x", pady=(0, 15), padx=5)
        
        # Display general notes
        if recommendations.get('notes'):
            notes_frame = ctk.CTkFrame(self.results_scroll_frame, corner_radius=8, fg_color="#374151")
            notes_frame.pack(fill="x", pady=(10, 0), padx=5)
            
            notes_label = ctk.CTkLabel(
                notes_frame,
                text=f"💡 {recommendations['notes']}",
                font=ctk.CTkFont(size=12),
                text_color="#D1D5DB",
                wraplength=550,
                justify="left"
            )
            notes_label.pack(padx=15, pady=15)
        
        # Save to history
        self.save_exercise_recommendation(recommendations, pain_description)
        
        self.set_status("Exercise recommendations generated successfully!", "green")

    # ===================================================================
    # TAB 11: Health Community (NEW SOCIAL COMMUNITY FEATURE)
    # ===================================================================
    def init_health_community_db(self):
        """Initialize health community database with JSON files."""
        try:
            # Initialize posts database
            if not os.path.exists("health_community_posts.json"):
                with open("health_community_posts.json", "w") as f:
                    json.dump([], f, indent=2)
            
            # Initialize friends database
            if not os.path.exists("health_community_friends.json"):
                with open("health_community_friends.json", "w") as f:
                    json.dump([], f, indent=2)
            
            # Initialize notifications database
            if not os.path.exists("health_community_notifications.json"):
                with open("health_community_notifications.json", "w") as f:
                    json.dump([], f, indent=2)
            
            # Add some sample posts for demonstration
            self.add_sample_posts()
            
            logging.info("Health Community database initialized successfully")
            
        except Exception as e:
            logging.error(f"Error initializing health community database: {e}")
            self.set_status(f"Error initializing community database: {e}", "red")

    def add_sample_posts(self):
        """Add sample posts for demonstration purposes."""
        try:
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Only add sample posts if none exist
                if not posts:
                    sample_posts = [
                        {
                            "id": "1",
                            "user": "Sarah Johnson",
                            "user_avatar": "sarah.png",
                            "timestamp": "2024-01-15T10:30:00",
                            "content": "Just completed my morning yoga session! 🧘‍♀️ Feeling energized and ready for the day. The sun salutation sequence really helps with my back flexibility.",
                            "benefits": "Improved flexibility, reduced back pain, better mood",
                            "media_path": "sample_yoga.jpg",
                            "media_type": "image",
                            "likes": 12,
                            "comments": [
                                {"user": "Mike Johnson", "text": "Great job Sarah! Yoga has been amazing for my stress levels too.", "timestamp": "2024-01-15T10:35:00"},
                                {"user": "Emma Johnson", "text": "I need to start doing this! What time do you usually practice?", "timestamp": "2024-01-15T10:40:00"}
                            ],
                            "shares": 3,
                            "category": "Yoga & Flexibility"
                        },
                        {
                            "id": "2",
                            "user": "Mike Johnson",
                            "user_avatar": "mike.png",
                            "timestamp": "2024-01-15T09:15:00",
                            "content": "Weekend workout complete! 💪 Hit a new personal record on deadlifts - 225 lbs for 5 reps. Consistency really pays off.",
                            "benefits": "Increased strength, better posture, confidence boost",
                            "media_path": "sample_workout.jpg",
                            "media_type": "image",
                            "likes": 18,
                            "comments": [
                                {"user": "Sarah Johnson", "text": "That's amazing Mike! You're getting so strong!", "timestamp": "2024-01-15T09:20:00"},
                                {"user": "Grandma Rose", "text": "Be careful with those heavy weights, dear!", "timestamp": "2024-01-15T09:25:00"}
                            ],
                            "shares": 5,
                            "category": "Strength Training"
                        },
                        {
                            "id": "3",
                            "user": "Emma Johnson",
                            "user_avatar": "emma.png",
                            "timestamp": "2024-01-15T08:00:00",
                            "content": "Healthy breakfast prep for the week! 🥗 Overnight oats with berries, chia seeds, and almond milk. Perfect for busy mornings.",
                            "benefits": "Saves time, nutritious start to the day, stable energy levels",
                            "media_path": "sample_breakfast.jpg",
                            "media_type": "image",
                            "likes": 25,
                            "comments": [
                                {"user": "Sarah Johnson", "text": "This looks delicious! Can you share the recipe?", "timestamp": "2024-01-15T08:05:00"},
                                {"user": "Mike Johnson", "text": "I need to start meal prepping like this!", "timestamp": "2024-01-15T08:10:00"}
                            ],
                            "shares": 8,
                            "category": "Nutrition & Meal Prep"
                        }
                    ]
                    
                    with open(posts_file, "w") as f:
                        json.dump(sample_posts, f, indent=2)
                    
                    logging.info("Sample posts added to health community")
            
        except Exception as e:
            logging.error(f"Error adding sample posts: {e}")

    def create_health_community_tab(self, tab):
        """Creates the health community social tab."""
        if not self.is_running:
            return
        
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Header with search and notifications
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame, 
            text="🏥 Health Community", 
            font=ctk.CTkFont(size=24, weight="bold"), 
            text_color="#FFFFFF"
        )
        title_label.grid(row=0, column=0, sticky="w")
        
        # Search bar
        search_frame = ctk.CTkFrame(header_frame, fg_color="#374151", corner_radius=20)
        search_frame.grid(row=0, column=1, padx=20, sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search friends, posts, or topics...",
            height=35,
            fg_color="transparent",
            border_width=0
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=15, pady=8)
        self.search_entry.bind("<Return>", self.search_community)
        
        # Notification bell
        self.notification_button = ctk.CTkButton(
            header_frame,
            text="🔔",
            width=40,
            height=35,
            fg_color="#3B82F6",
            hover_color="#60A5FA",
            command=self.show_notifications
        )
        self.notification_button.grid(row=0, column=2, padx=(10, 0))
        
        # Create post button
        create_post_button = ctk.CTkButton(
            header_frame,
            text="✏️ Create Post",
            height=35,
            fg_color="#27AE60",
            hover_color="#22C55E",
            command=self.show_create_post_dialog
        )
        create_post_button.grid(row=0, column=3, padx=(10, 0))
        
        # Main content area
        content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        content_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=3)
        content_frame.grid_columnconfigure(1, weight=1)
        
        # Posts feed (left side)
        feed_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2B2B2B")
        feed_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="nsew")
        feed_frame.grid_columnconfigure(0, weight=1)
        feed_frame.grid_rowconfigure(1, weight=1)
        
        feed_header = ctk.CTkLabel(
            feed_frame,
            text="📱 Community Feed",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF"
        )
        feed_header.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="w")
        
        # Scrollable feed
        self.feed_scroll_frame = ctk.CTkScrollableFrame(feed_frame, fg_color="transparent")
        self.feed_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.feed_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Right sidebar
        sidebar_frame = ctk.CTkFrame(content_frame, corner_radius=10, fg_color="#2B2B2B")
        sidebar_frame.grid(row=0, column=1, pady=0, sticky="nsew")
        sidebar_frame.grid_columnconfigure(0, weight=1)
        sidebar_frame.grid_rowconfigure(1, weight=1)
        
        sidebar_header = ctk.CTkLabel(
            sidebar_frame,
            text="👥 Friends & Activity",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        sidebar_header.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        
        # Friends list
        self.friends_scroll_frame = ctk.CTkScrollableFrame(sidebar_frame, fg_color="transparent")
        self.friends_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.friends_scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Load initial content
        self.load_community_feed()
        self.load_friends_list()

    def load_community_feed(self):
        """Load and display the community feed."""
        if not self.is_running:
            return
        
        try:
            # Clear existing feed
            for widget in self.feed_scroll_frame.winfo_children():
                widget.destroy()
            
            # Load posts from database
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Sort posts by timestamp (newest first)
                posts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                
                # Display each post
                for post in posts:
                    post_card = self.create_post_card(post)
                    post_card.pack(fill="x", pady=(0, 15), padx=5)
                    
                    # Add fade-in animation
                    post_card.configure(fg_color="#374151")
                    self.after(100, lambda card=post_card: self.animate_post_card(card))
            else:
                # Show no posts message
                no_posts_label = ctk.CTkLabel(
                    self.feed_scroll_frame,
                    text="No posts yet. Be the first to share your health journey!",
                    font=ctk.CTkFont(size=14),
                    text_color="#9CA3AF"
                )
                no_posts_label.pack(pady=50)
                
        except Exception as e:
            logging.error(f"Error loading community feed: {e}")
            error_label = ctk.CTkLabel(
                self.feed_scroll_frame,
                text=f"Error loading feed: {e}",
                font=ctk.CTkFont(size=14),
                text_color="#EF4444"
            )
            error_label.pack(pady=50)

    def load_friends_list(self):
        """Load and display the friends list."""
        if not self.is_running:
            return
        
        try:
            # Clear existing friends list
            for widget in self.friends_scroll_frame.winfo_children():
                widget.destroy()
            
            # Mock friends list for demonstration
            friends = [
                {"name": "Sarah Johnson", "avatar": "sarah.png", "status": "Active", "last_activity": "2 hours ago"},
                {"name": "Mike Johnson", "avatar": "mike.png", "status": "Active", "last_activity": "1 hour ago"},
                {"name": "Emma Johnson", "avatar": "emma.png", "status": "Active", "last_activity": "30 min ago"},
                {"name": "Grandma Rose", "avatar": "rose.png", "status": "Away", "last_activity": "1 day ago"}
            ]
            
            # Add friends
            for friend in friends:
                friend_card = self.create_friend_card(friend)
                friend_card.pack(fill="x", pady=(0, 10), padx=5)
            
            # Add friend button
            add_friend_button = ctk.CTkButton(
                self.friends_scroll_frame,
                text="+ Add Friend",
                fg_color="transparent",
                border_width=1,
                border_color="#3B82F6",
                text_color="#3B82F6",
                hover_color="#1F2937",
                command=self.show_add_friend_dialog
            )
            add_friend_button.pack(fill="x", pady=(10, 0), padx=5)
            
        except Exception as e:
            logging.error(f"Error loading friends list: {e}")
            error_label = ctk.CTkLabel(
                self.friends_scroll_frame,
                text=f"Error loading friends: {e}",
                font=ctk.CTkFont(size=12),
                text_color="#EF4444"
            )
            error_label.pack(pady=20)

    def animate_post_card(self, card):
        """Animate post card with fade-in effect."""
        try:
            card.configure(fg_color="#2B2B2B")
        except Exception as e:
            logging.error(f"Error animating post card: {e}")

    def create_post_card(self, post):
        """Create a card widget for displaying a post."""
        card = ctk.CTkFrame(self.feed_scroll_frame, corner_radius=10, fg_color="#2B2B2B")
        card.grid_columnconfigure(1, weight=1)
        
        # Post header with user info
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # User avatar
        avatar_path = os.path.join("member_photos", post.get("user_avatar", "sarah.png"))
        try:
            avatar_img = Image.open(avatar_path)
            avatar_img.thumbnail((40, 40), Image.Resampling.LANCZOS)
            ctk_avatar = ctk.CTkImage(light_image=avatar_img, dark_image=avatar_img, size=(40, 40))
            avatar_label = ctk.CTkLabel(header_frame, image=ctk_avatar, text="")
        except:
            # Fallback avatar
            avatar_label = ctk.CTkLabel(
                header_frame,
                text="👤",
                font=ctk.CTkFont(size=20),
                width=40,
                height=40,
                fg_color="#374151",
                corner_radius=20
            )
        
        avatar_label.grid(row=0, column=0, padx=(0, 10))
        
        # User info
        user_label = ctk.CTkLabel(
            header_frame,
            text=post.get("user", "Unknown User"),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FFFFFF"
        )
        user_label.grid(row=0, column=1, sticky="w")
        
        # Timestamp
        timestamp = post.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                time_ago = self.get_time_ago(dt)
                time_label = ctk.CTkLabel(
                    header_frame,
                    text=time_ago,
                    font=ctk.CTkFont(size=10),
                    text_color="#9CA3AF"
                )
                time_label.grid(row=1, column=1, sticky="w")
            except:
                pass
        
        # Category badge
        category = post.get("category", "")
        if category:
            category_label = ctk.CTkLabel(
                header_frame,
                text=category,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="white",
                fg_color="#3B82F6",
                corner_radius=10,
                width=80,
                height=20
            )
            category_label.grid(row=0, column=2, padx=(10, 0))
        
        # Post content
        content_label = ctk.CTkLabel(
            card,
            text=post.get("content", ""),
            font=ctk.CTkFont(size=13),
            text_color="#D1D5DB",
            wraplength=500,
            justify="left"
        )
        content_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 10))
        
        # Benefits section
        benefits = post.get("benefits", "")
        if benefits:
            benefits_frame = ctk.CTkFrame(card, fg_color="#374151", corner_radius=8)
            benefits_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 10))
            
            benefits_label = ctk.CTkLabel(
                benefits_frame,
                text=f"💪 Benefits: {benefits}",
                font=ctk.CTkFont(size=11),
                text_color="#22C55E",
                wraplength=480
            )
            benefits_label.pack(padx=10, pady=8)
        
        # Media content (if any)
        media_path = post.get("media_path", "")
        media_type = post.get("media_type", "")
        
        if media_path and media_type == "image":
            try:
                # For demo, create a placeholder image
                media_label = ctk.CTkLabel(
                    card,
                    text="🖼️",
                    font=ctk.CTkFont(size=40),
                    text_color="#9CA3AF",
                    width=200,
                    height=150,
                    fg_color="#374151",
                    corner_radius=8
                )
                media_label.grid(row=3, column=0, columnspan=3, padx=15, pady=(0, 10))
            except Exception as e:
                logging.error(f"Error displaying media: {e}")
        
        # Interaction buttons
        interactions_frame = ctk.CTkFrame(card, fg_color="transparent")
        interactions_frame.grid(row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 15))
        interactions_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Like button
        like_count = post.get("likes", 0)
        like_button = ctk.CTkButton(
            interactions_frame,
            text=f"❤️ {like_count}",
            fg_color="transparent",
            border_width=1,
            border_color="#EF4444",
            text_color="#EF4444",
            hover_color="#1F2937",
            height=30,
            command=lambda p=post: self.like_post(p)
        )
        like_button.grid(row=0, column=0, padx=(0, 5))
        
        # Comment button
        comment_count = len(post.get("comments", []))
        comment_button = ctk.CTkButton(
            interactions_frame,
            text=f"💬 {comment_count}",
            fg_color="transparent",
            border_width=1,
            border_color="#3B82F6",
            text_color="#3B82F6",
            hover_color="#1F2937",
            height=30,
            command=lambda p=post: self.show_comments_dialog(p)
        )
        comment_button.grid(row=0, column=1, padx=5)
        
        # Share button
        share_count = post.get("shares", 0)
        share_button = ctk.CTkButton(
            interactions_frame,
            text=f"📤 {share_count}",
            fg_color="transparent",
            border_width=1,
            border_color="#27AE60",
            text_color="#27AE60",
            hover_color="#1F2937",
            height=30,
            command=lambda p=post: self.share_post(p)
        )
        share_button.grid(row=0, column=2, padx=5)
        
        # Follow Routine button
        follow_button = ctk.CTkButton(
            interactions_frame,
            text="📋 Follow Routine",
            fg_color="#F59E0B",
            hover_color="#D97706",
            height=30,
            command=lambda p=post: self.follow_routine(p)
        )
        follow_button.grid(row=0, column=3, padx=(5, 0))
        
        return card

    def create_friend_card(self, friend):
        """Create a card widget for displaying friend information."""
        card = ctk.CTkFrame(self.friends_scroll_frame, corner_radius=8, fg_color="#374151")
        card.grid_columnconfigure(1, weight=1)
        
        # Friend avatar
        avatar_path = os.path.join("member_photos", friend.get("avatar", "sarah.png"))
        try:
            avatar_img = Image.open(avatar_path)
            avatar_img.thumbnail((35, 35), Image.Resampling.LANCZOS)
            ctk_avatar = ctk.CTkImage(light_image=avatar_img, dark_image=avatar_img, size=(35, 35))
            avatar_label = ctk.CTkLabel(card, image=ctk_avatar, text="")
        except:
            avatar_label = ctk.CTkLabel(
                card,
                text="👤",
                font=ctk.CTkFont(size=16),
                width=35,
                height=35,
                fg_color="#2B2B2B",
                corner_radius=17
            )
        
        avatar_label.grid(row=0, column=0, padx=10, pady=10)
        
        # Friend info
        name_label = ctk.CTkLabel(
            card,
            text=friend.get("name", "Unknown"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFFFFF"
        )
        name_label.grid(row=0, column=1, sticky="w", pady=(10, 2))
        
        status_label = ctk.CTkLabel(
            card,
            text=f"{friend.get('status', 'Unknown')} • {friend.get('last_activity', 'Unknown')}",
            font=ctk.CTkFont(size=10),
            text_color="#9CA3AF"
        )
        status_label.grid(row=1, column=1, sticky="w", pady=(0, 10))
        
        return card

    def get_time_ago(self, dt):
        """Get human-readable time ago string."""
        try:
            now = datetime.datetime.now()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                return "Just now"
        except:
            return "Unknown time"

    def like_post(self, post):
        """Like a post."""
        try:
            # Update post likes
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Find and update the post
                for p in posts:
                    if p.get("id") == post.get("id"):
                        p["likes"] = p.get("likes", 0) + 1
                        break
                
                # Save updated posts
                with open(posts_file, "w") as f:
                    json.dump(posts, f, indent=2)
                
                # Add notification
                self.add_notification(
                    post.get("user", "Unknown"),
                    f"{self.current_user} liked your post about {post.get('category', 'health')}!"
                )
                
                # Refresh feed
                self.load_community_feed()
                
                self.set_status("Post liked!", "green")
                logging.info(f"Post {post.get('id')} liked by {self.current_user}")
                
        except Exception as e:
            logging.error(f"Error liking post: {e}")
            self.set_status(f"Error liking post: {e}", "red")

    def show_comments_dialog(self, post):
        """Show comments dialog for a post."""
        try:
            # Create popup window
            dialog = ctk.CTkToplevel(self)
            dialog.title("Comments")
            dialog.geometry("500x400")
            dialog.transient(self)
            dialog.grab_set()
            
            # Header
            header_label = ctk.CTkLabel(
                dialog,
                text=f"💬 Comments on {post.get('user', 'Unknown')}'s post",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            header_label.pack(pady=15)
            
            # Comments display
            comments_frame = ctk.CTkScrollableFrame(dialog, height=200)
            comments_frame.pack(fill="x", padx=20, pady=(0, 20))
            
            # Show existing comments
            comments = post.get("comments", [])
            for comment in comments:
                comment_text = f"{comment['user']}: {comment['text']}"
                comment_label = ctk.CTkLabel(
                    comments_frame,
                    text=comment_text,
                    wraplength=400,
                    justify="left"
                )
                comment_label.pack(anchor="w", pady=5)
            
            # Add new comment
            input_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            input_frame.pack(fill="x", padx=20, pady=(0, 20))
            input_frame.grid_columnconfigure(0, weight=1)
            
            comment_entry = ctk.CTkEntry(
                input_frame,
                placeholder_text="Add a comment...",
                height=35
            )
            comment_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
            
            add_button = ctk.CTkButton(
                input_frame,
                text="Add Comment",
                command=lambda: self.add_comment(post, comment_entry.get().strip(), dialog),
                height=35,
                fg_color="#3B82F6",
                hover_color="#60A5FA"
            )
            add_button.grid(row=0, column=1)
            
        except Exception as e:
            logging.error(f"Error showing comments dialog: {e}")
            self.set_status(f"Error showing comments: {e}", "red")

    def add_comment(self, post, comment_text, dialog):
        """Add a comment to a post."""
        if not comment_text.strip():
            return
        
        try:
            # Update post comments
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Find and update the post
                for p in posts:
                    if p.get("id") == post.get("id"):
                        if "comments" not in p:
                            p["comments"] = []
                        
                        new_comment = {
                            "user": self.current_user,
                            "text": comment_text,
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                        p["comments"].append(new_comment)
                        break
                
                # Save updated posts
                with open(posts_file, "w") as f:
                    json.dump(posts, f, indent=2)
                
                # Add notification
                self.add_notification(
                    post.get("user", "Unknown"),
                    f"{self.current_user} commented on your post: '{comment_text[:30]}...'"
                )
                
                # Close dialog and refresh feed
                dialog.destroy()
                self.load_community_feed()
                
                self.set_status("Comment added!", "green")
                logging.info(f"Comment added to post {post.get('id')} by {self.current_user}")
                
        except Exception as e:
            logging.error(f"Error adding comment: {e}")
            self.set_status(f"Error adding comment: {e}", "red")

    def share_post(self, post):
        """Share a post."""
        try:
            # For now, just increment share count
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Find and update the post
                for p in posts:
                    if p.get("id") == post.get("id"):
                        p["shares"] = p.get("shares", 0) + 1
                        break
                
                # Save updated posts
                with open(posts_file, "w") as f:
                    json.dump(posts, f, indent=2)
                
                # Add notification
                self.add_notification(
                    post.get("user", "Unknown"),
                    f"{self.current_user} shared your post about {post.get('category', 'health')}!"
                )
                
                # Refresh feed
                self.load_community_feed()
                
                self.set_status("Post shared!", "green")
                logging.info(f"Post {post.get('id')} shared by {self.current_user}")
                
        except Exception as e:
            logging.error(f"Error sharing post: {e}")
            self.set_status(f"Error sharing post: {e}", "red")

    def follow_routine(self, post):
        """Follow a routine from a post using AI."""
        try:
            self.set_status("Analyzing routine with AI...", "blue")
            
            # Use Gemini API to analyze the post and create a personalized routine
            routine = self.generate_personalized_routine(post)
            
            if routine:
                # Show routine dialog
                self.show_routine_dialog(post, routine)
            else:
                self.set_status("Could not generate routine. Please try again.", "red")
                
        except Exception as e:
            logging.error(f"Error following routine: {e}")
            self.set_status(f"Error following routine: {e}", "red")

    def generate_personalized_routine(self, post):
        """Generate a personalized routine using Gemini API."""
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            You are an expert health and fitness coach. Based on the following social media post, create a personalized routine for the user.
            
            Post Content: {post.get('content', '')}
            Benefits Mentioned: {post.get('benefits', '')}
            Category: {post.get('category', '')}
            
            Create a personalized routine that includes:
            1. Warm-up exercises
            2. Main routine (3-5 exercises/activities)
            3. Cool-down
            4. Frequency and duration recommendations
            5. Safety tips
            
            Respond in JSON format:
            {{
                "routine_name": "string",
                "description": "string",
                "warm_up": ["exercise1", "exercise2"],
                "main_routine": [
                    {{
                        "exercise": "string",
                        "duration": "string",
                        "reps": "string",
                        "tips": "string"
                    }}
                ],
                "cool_down": ["exercise1", "exercise2"],
                "frequency": "string",
                "duration": "string",
                "safety_tips": ["tip1", "tip2"],
                "personalization": "string"
            }}
            
            Make it engaging and motivational, suitable for the user's current fitness level.
            """
            
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            
            # Parse JSON response
            routine = json.loads(json_text)
            
            # Validate response structure
            required_fields = ["routine_name", "description", "main_routine"]
            if not all(field in routine for field in required_fields):
                raise ValueError("Invalid routine structure from AI")
            
            return routine
            
        except Exception as e:
            print(f"AI API Error: {e}")
            # Return fallback routine
            return {
                "routine_name": f"Personalized {post.get('category', 'Health')} Routine",
                "description": f"Based on {post.get('user', 'Unknown')}'s post about {post.get('category', 'health')}",
                "warm_up": ["Light stretching", "Deep breathing", "Gentle movements"],
                "main_routine": [
                    {
                        "exercise": "Adapted exercise from post",
                        "duration": "10-15 minutes",
                        "reps": "3 sets",
                        "tips": "Start slowly and listen to your body"
                    }
                ],
                "cool_down": ["Stretching", "Relaxation"],
                "frequency": "3-4 times per week",
                "duration": "30-45 minutes total",
                "safety_tips": ["Consult a professional if needed", "Stop if you feel pain"],
                "personalization": "This routine has been adapted for your fitness level and goals."
            }

    def show_routine_dialog(self, post, routine):
        """Show the generated routine dialog."""
        try:
            # Create popup window
            dialog = ctk.CTkToplevel(self)
            dialog.title("Your Personalized Routine")
            dialog.geometry("600x500")
            dialog.transient(self)
            dialog.grab_set()
            
            # Make popup scrollable
            scroll_frame = ctk.CTkScrollableFrame(dialog)
            scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Routine header
            header_label = ctk.CTkLabel(
                scroll_frame,
                text=f"📋 {routine['routine_name']}",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#3B82F6"
            )
            header_label.pack(pady=(0, 10))
            
            # Description
            desc_label = ctk.CTkLabel(
                scroll_frame,
                text=routine['description'],
                wraplength=500,
                justify="left"
            )
            desc_label.pack(pady=(0, 20))
            
            # Warm-up section
            warmup_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
            warmup_frame.pack(fill="x", pady=(0, 15), padx=5)
            
            ctk.CTkLabel(
                warmup_frame,
                text="🔥 Warm-up",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#F59E0B"
            ).pack(anchor="w", padx=15, pady=(10, 5))
            
            for exercise in routine['warm_up']:
                ctk.CTkLabel(
                    warmup_frame,
                    text=f"• {exercise}",
                    anchor="w"
                ).pack(anchor="w", padx=25, pady=2)
            
            ctk.CTkLabel(warmup_frame, text="").pack(pady=5)
            
            # Main routine section
            main_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
            main_frame.pack(fill="x", pady=(0, 15), padx=5)
            
            ctk.CTkLabel(
                main_frame,
                text="💪 Main Routine",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#27AE60"
            ).pack(anchor="w", padx=15, pady=(10, 5))
            
            for exercise in routine['main_routine']:
                exercise_frame = ctk.CTkFrame(main_frame, fg_color="#2B2B2B", corner_radius=5)
                exercise_frame.pack(fill="x", padx=15, pady=5)
                
                ctk.CTkLabel(
                    exercise_frame,
                    text=f"🏃 {exercise['exercise']}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#FFFFFF"
                ).pack(anchor="w", padx=10, pady=(5, 2))
                
                ctk.CTkLabel(
                    exercise_frame,
                    text=f"Duration: {exercise['duration']} | Reps: {exercise['reps']}",
                    font=ctk.CTkFont(size=10),
                    text_color="#9CA3AF"
                ).pack(anchor="w", padx=10, pady=(0, 5))
                
                if 'tips' in exercise:
                    ctk.CTkLabel(
                        exercise_frame,
                        text=f"💡 {exercise['tips']}",
                        font=ctk.CTkFont(size=10),
                        text_color="#60A5FA",
                        wraplength=450
                    ).pack(anchor="w", padx=10, pady=(0, 5))
            
            # Cool-down section
            cooldown_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
            cooldown_frame.pack(fill="x", pady=(0, 15), padx=5)
            
            ctk.CTkLabel(
                cooldown_frame,
                text="🧘 Cool-down",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#8B5CF6"
            ).pack(anchor="w", padx=15, pady=(10, 5))
            
            for exercise in routine['cool_down']:
                ctk.CTkLabel(
                    cooldown_frame,
                    text=f"• {exercise}",
                    anchor="w"
                ).pack(anchor="w", padx=25, pady=2)
            
            ctk.CTkLabel(cooldown_frame, text="").pack(pady=5)
            
            # Frequency and duration
            info_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
            info_frame.pack(fill="x", pady=(0, 15), padx=5)
            
            ctk.CTkLabel(
                info_frame,
                text=f"📅 Frequency: {routine['frequency']}",
                anchor="w"
            ).pack(anchor="w", padx=15, pady=(10, 2))
            
            ctk.CTkLabel(
                info_frame,
                text=f"⏱️ Duration: {routine['duration']}",
                anchor="w"
            ).pack(anchor="w", padx=15, pady=(0, 10))
            
            # Safety tips
            if 'safety_tips' in routine and routine['safety_tips']:
                safety_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
                safety_frame.pack(fill="x", pady=(0, 15), padx=5)
                
                ctk.CTkLabel(
                    safety_frame,
                    text="⚠️ Safety Tips",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color="#EF4444"
                ).pack(anchor="w", padx=15, pady=(10, 5))
                
                for tip in routine['safety_tips']:
                    ctk.CTkLabel(
                        safety_frame,
                        text=f"• {tip}",
                        anchor="w",
                        wraplength=450
                    ).pack(anchor="w", padx=25, pady=2)
                
                ctk.CTkLabel(safety_frame, text="").pack(pady=5)
            
            # Personalization note
            if 'personalization' in routine:
                personal_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#1F2937")
                personal_frame.pack(fill="x", pady=(0, 15), padx=5)
                
                ctk.CTkLabel(
                    personal_frame,
                    text=f"🎯 {routine['personalization']}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="#60A5FA",
                    wraplength=500
                ).pack(padx=15, pady=10)
            
            # Action buttons
            button_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(10, 0), padx=5)
            button_frame.grid_columnconfigure((0, 1), weight=1)
            
            save_button = ctk.CTkButton(
                button_frame,
                text="💾 Save to Profile",
                command=lambda: self.save_routine_to_profile(routine, dialog),
                fg_color="#27AE60",
                hover_color="#22C55E"
            )
            save_button.grid(row=0, column=0, padx=(0, 5))
            
            close_button = ctk.CTkButton(
                button_frame,
                text="Close",
                command=dialog.destroy,
                fg_color="transparent",
                border_width=1,
                border_color="#6B7280",
                text_color="#6B7280"
            )
            close_button.grid(row=0, column=1, padx=(5, 0))
            
        except Exception as e:
            logging.error(f"Error showing routine dialog: {e}")
            self.set_status(f"Error showing routine: {e}", "red")

    def save_routine_to_profile(self, routine, dialog):
        """Save the generated routine to user's profile."""
        try:
            # Save routine to profile data
            if "routines" not in self.profile_data:
                self.profile_data["routines"] = []
            
            routine_data = {
                "id": f"routine_{len(self.profile_data['routines']) + 1}",
                "name": routine['routine_name'],
                "description": routine['description'],
                "created_date": datetime.datetime.now().isoformat(),
                "routine": routine
            }
            
            self.profile_data["routines"].append(routine_data)
            self.save_profile()
            
            dialog.destroy()
            self.set_status("Routine saved to your profile!", "green")
            logging.info(f"Routine saved to profile by {self.current_user}")
            
        except Exception as e:
            logging.error(f"Error saving routine to profile: {e}")
            self.set_status(f"Error saving routine: {e}", "red")

    def add_notification(self, user, message):
        """Add a notification for a user."""
        try:
            notifications_file = "health_community_notifications.json"
            notifications = []
            
            if os.path.exists(notifications_file):
                with open(notifications_file, "r") as f:
                    notifications = json.load(f)
            
            new_notification = {
                "id": f"notif_{len(notifications) + 1}",
                "user": user,
                "message": message,
                "timestamp": datetime.datetime.now().isoformat(),
                "read": False
            }
            
            notifications.append(new_notification)
            
            # Keep only last 50 notifications
            if len(notifications) > 50:
                notifications = notifications[-50:]
            
            with open(notifications_file, "w") as f:
                json.dump(notifications, f, indent=2)
                
        except Exception as e:
            logging.error(f"Error adding notification: {e}")

    def show_notifications(self):
        """Show notifications popup."""
        try:
            # Create popup window
            dialog = ctk.CTkToplevel(self)
            dialog.title("Notifications")
            dialog.geometry("400x300")
            dialog.transient(self)
            dialog.grab_set()
            
            # Header
            header_label = ctk.CTkLabel(
                dialog,
                text="🔔 Notifications",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            header_label.pack(pady=15)
            
            # Notifications display
            notifications_frame = ctk.CTkScrollableFrame(dialog, height=200)
            notifications_frame.pack(fill="x", padx=20, pady=(0, 20))
            
            # Load notifications
            notifications_file = "health_community_notifications.json"
            if os.path.exists(notifications_file):
                with open(notifications_file, "r") as f:
                    notifications = json.load(f)
                
                # Show recent notifications (last 10)
                recent_notifications = notifications[-10:] if len(notifications) > 10 else notifications
                
                for notification in reversed(recent_notifications):
                    notif_text = f"{notification['message']}"
                    notif_label = ctk.CTkLabel(
                        notifications_frame,
                        text=notif_text,
                        wraplength=350,
                        justify="left"
                    )
                    notif_label.pack(anchor="w", pady=5)
                    
                    # Timestamp
                    try:
                        dt = datetime.datetime.fromisoformat(notification['timestamp'])
                        time_ago = self.get_time_ago(dt)
                        time_label = ctk.CTkLabel(
                            notifications_frame,
                            text=time_ago,
                            font=ctk.CTkFont(size=10),
                            text_color="#9CA3AF"
                        )
                        time_label.pack(anchor="w", pady=(0, 10))
                    except:
                        pass
            else:
                no_notif_label = ctk.CTkLabel(
                    notifications_frame,
                    text="No notifications yet.",
                    text_color="#9CA3AF"
                )
                no_notif_label.pack(pady=20)
            
        except Exception as e:
            logging.error(f"Error showing notifications: {e}")
            self.set_status(f"Error showing notifications: {e}", "red")

    def search_community(self, event=None):
        """Search the community for posts, users, or topics."""
        search_term = self.search_entry.get().strip().lower()
        if not search_term:
            self.load_community_feed()
            return
        
        try:
            # Clear existing feed
            for widget in self.feed_scroll_frame.winfo_children():
                widget.destroy()
            
            # Load posts and filter
            posts_file = "health_community_posts.json"
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
                
                # Filter posts based on search term
                filtered_posts = []
                for post in posts:
                    if (search_term in post.get("content", "").lower() or
                        search_term in post.get("benefits", "").lower() or
                        search_term in post.get("category", "").lower() or
                        search_term in post.get("user", "").lower()):
                        filtered_posts.append(post)
                
                if filtered_posts:
                    # Sort by timestamp (newest first)
                    filtered_posts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                    
                    # Display filtered posts
                    for post in filtered_posts:
                        post_card = self.create_post_card(post)
                        post_card.pack(fill="x", pady=(0, 15), padx=5)
                        
                        # Add fade-in animation
                        post_card.configure(fg_color="#374151")
                        self.after(100, lambda card=post_card: self.animate_post_card(card))
                    
                    self.set_status(f"Found {len(filtered_posts)} posts matching '{search_term}'", "green")
                else:
                    no_results_label = ctk.CTkLabel(
                        self.feed_scroll_frame,
                        text=f"No posts found matching '{search_term}'",
                        font=ctk.CTkFont(size=14),
                        text_color="#9CA3AF"
                    )
                    no_results_label.pack(pady=50)
                    
                    self.set_status(f"No results found for '{search_term}'", "blue")
            else:
                no_posts_label = ctk.CTkLabel(
                    self.feed_scroll_frame,
                    text="No posts available for search.",
                    font=ctk.CTkFont(size=14),
                    text_color="#9CA3AF"
                )
                no_posts_label.pack(pady=50)
                
        except Exception as e:
            logging.error(f"Error searching community: {e}")
            error_label = ctk.CTkLabel(
                self.feed_scroll_frame,
                text=f"Error searching: {e}",
                font=ctk.CTkFont(size=14),
                text_color="#EF4444"
            )
            error_label.pack(pady=50)

    def show_create_post_dialog(self):
        """Show dialog to create a new post."""
        try:
            # Create popup window
            dialog = ctk.CTkToplevel(self)
            dialog.title("Create New Post")
            dialog.geometry("500x600")
            dialog.transient(self)
            dialog.grab_set()
            
            # Header
            header_label = ctk.CTkLabel(
                dialog,
                text="✏️ Share Your Health Journey",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#27AE60"
            )
            header_label.pack(pady=15)
            
            # Content input
            content_label = ctk.CTkLabel(
                dialog,
                text="What did you do today?",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            content_label.pack(anchor="w", padx=20, pady=(0, 5))
            
            content_textbox = ctk.CTkTextbox(
                dialog,
                height=100,
                placeholder_text="Describe your activity, workout, meal, or progress..."
            )
            content_textbox.pack(fill="x", padx=20, pady=(0, 15))
            
            # Benefits input
            benefits_label = ctk.CTkLabel(
                dialog,
                text="What benefits did you experience?",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            benefits_label.pack(anchor="w", padx=20, pady=(0, 5))
            
            benefits_textbox = ctk.CTkTextbox(
                dialog,
                height=80,
                placeholder_text="e.g., Increased energy, better mood, weight loss..."
            )
            benefits_textbox.pack(fill="x", padx=20, pady=(0, 15))
            
            # Category selection
            category_label = ctk.CTkLabel(
                dialog,
                text="Category:",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            category_label.pack(anchor="w", padx=20, pady=(0, 5))
            
            categories = [
                "Yoga & Flexibility", "Strength Training", "Cardio & Endurance",
                "Nutrition & Meal Prep", "Mental Health", "Recovery & Rest",
                "Weight Loss", "Muscle Building", "General Wellness"
            ]
            
            category_var = ctk.StringVar(value=categories[0])
            category_dropdown = ctk.CTkOptionMenu(
                dialog,
                values=categories,
                variable=category_var
            )
            category_dropdown.pack(anchor="w", padx=20, pady=(0, 15))
            
            # Media upload (placeholder for now)
            media_label = ctk.CTkLabel(
                dialog,
                text="📷 Media Upload (Coming Soon)",
                font=ctk.CTkFont(size=12),
                text_color="#9CA3AF"
            )
            media_label.pack(anchor="w", padx=20, pady=(0, 15))
            
            # Action buttons
            button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=(0, 20))
            button_frame.grid_columnconfigure((0, 1), weight=1)
            
            post_button = ctk.CTkButton(
                button_frame,
                text="📤 Share Post",
                command=lambda: self.create_post(
                    content_textbox.get("1.0", "end").strip(),
                    benefits_textbox.get("1.0", "end").strip(),
                    category_var.get(),
                    dialog
                ),
                fg_color="#27AE60",
                hover_color="#22C55E"
            )
            post_button.grid(row=0, column=0, padx=(0, 5))
            
            cancel_button = ctk.CTkButton(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                fg_color="transparent",
                border_width=1,
                border_color="#6B7280",
                text_color="#6B7280"
            )
            cancel_button.grid(row=0, column=1, padx=(5, 0))
            
        except Exception as e:
            logging.error(f"Error showing create post dialog: {e}")
            self.set_status(f"Error showing dialog: {e}", "red")

    def create_post(self, content, benefits, category, dialog):
        """Create a new post."""
        if not content.strip():
            self.set_status("Please enter some content for your post.", "red")
            return
        
        try:
            # Generate unique post ID
            posts_file = "health_community_posts.json"
            posts = []
            
            if os.path.exists(posts_file):
                with open(posts_file, "r") as f:
                    posts = json.load(f)
            
            new_post_id = str(len(posts) + 1)
            
            # Create new post
            new_post = {
                "id": new_post_id,
                "user": self.current_user,
                "user_avatar": "user.png",  # Default avatar
                "timestamp": datetime.datetime.now().isoformat(),
                "content": content,
                "benefits": benefits,
                "media_path": "",
                "media_type": "",
                "likes": 0,
                "comments": [],
                "shares": 0,
                "category": category
            }
            
            # Add to posts
            posts.append(new_post)
            
            # Save to file
            with open(posts_file, "w") as f:
                json.dump(posts, f, indent=2)
            
            # Close dialog and refresh feed
            dialog.destroy()
            self.load_community_feed()
            
            self.set_status("Post created successfully!", "green")
            logging.info(f"New post created by {self.current_user}")
            
        except Exception as e:
            logging.error(f"Error creating post: {e}")
            self.set_status(f"Error creating post: {e}", "red")

    def show_add_friend_dialog(self):
        """Show dialog to add a friend."""
        try:
            # Create popup window
            dialog = ctk.CTkToplevel(self)
            dialog.title("Add Friend")
            dialog.geometry("300x200")
            dialog.transient(self)
            dialog.grab_set()
            
            # Header
            header_label = ctk.CTkLabel(
                dialog,
                text="👥 Add New Friend",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            header_label.pack(pady=15)
            
            # Username input
            username_label = ctk.CTkLabel(
                dialog,
                text="Username:",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            username_label.pack(anchor="w", padx=20, pady=(0, 5))
            
            username_entry = ctk.CTkEntry(
                dialog,
                placeholder_text="Enter username...",
                height=35
            )
            username_entry.pack(fill="x", padx=20, pady=(0, 20))
            
            # Action buttons
            button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            button_frame.pack(fill="x", padx=20, pady=(0, 20))
            button_frame.grid_columnconfigure((0, 1), weight=1)
            
            add_button = ctk.CTkButton(
                button_frame,
                text="Add Friend",
                command=lambda: self.add_friend(username_entry.get().strip(), dialog),
                fg_color="#3B82F6",
                hover_color="#60A5FA"
            )
            add_button.grid(row=0, column=0, padx=(0, 5))
            
            cancel_button = ctk.CTkButton(
                button_frame,
                text="Cancel",
                command=dialog.destroy,
                fg_color="transparent",
                border_width=1,
                border_color="#6B7280",
                text_color="#6B7280"
            )
            cancel_button.grid(row=0, column=1, padx=(5, 0))
            
        except Exception as e:
            logging.error(f"Error showing add friend dialog: {e}")
            self.set_status(f"Error showing dialog: {e}", "red")

    def add_friend(self, username, dialog):
        """Add a friend to the user's network."""
        if not username.strip():
            self.set_status("Please enter a username.", "red")
            return
        
        try:
            # For demo purposes, just show success message
            # In a real app, you'd validate the username and add to friends database
            
            dialog.destroy()
            self.set_status(f"Friend request sent to {username}!", "green")
            logging.info(f"Friend request sent to {username} by {self.current_user}")
            
        except Exception as e:
            logging.error(f"Error adding friend: {e}")
            self.set_status(f"Error adding friend: {e}", "red")

    def create_exercise_card(self, exercise, index):
        """Create a card widget for displaying exercise information."""
        card = ctk.CTkFrame(self.results_scroll_frame, corner_radius=10, fg_color="#374151")
        card.grid_columnconfigure(1, weight=1)
        
        # Exercise number and name
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 10))
        header_frame.grid_columnconfigure(1, weight=1)
        
        number_label = ctk.CTkLabel(
            header_frame,
            text=f"{index}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#3B82F6",
            width=30
        )
        number_label.grid(row=0, column=0, padx=(0, 10))
        
        name_label = ctk.CTkLabel(
            header_frame,
            text=exercise['name'],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF"
        )
        name_label.grid(row=0, column=1, sticky="w")
        
        # Difficulty and duration badges
        difficulty_color = "#22C55E" if exercise.get('difficulty') == "Beginner" else "#F59E0B" if exercise.get('difficulty') == "Intermediate" else "#EF4444"
        difficulty_label = ctk.CTkLabel(
            header_frame,
            text=exercise.get('difficulty', 'N/A'),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color=difficulty_color,
            corner_radius=10,
            width=80,
            height=20
        )
        difficulty_label.grid(row=0, column=2, padx=(10, 0))
        
        # Description
        desc_label = ctk.CTkLabel(
            card,
            text=exercise['description'],
            font=ctk.CTkFont(size=13),
            text_color="#D1D5DB",
            wraplength=500,
            justify="left"
        )
        desc_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=15, pady=(0, 10))
        
        # Duration and frequency
        details_frame = ctk.CTkFrame(card, fg_color="transparent")
        details_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 15))
        details_frame.grid_columnconfigure((0, 1), weight=1)
        
        duration_label = ctk.CTkLabel(
            details_frame,
            text=f"⏱️ Duration: {exercise.get('duration', 'N/A')}",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        duration_label.grid(row=0, column=0, sticky="w")
        
        frequency_label = ctk.CTkLabel(
            details_frame,
            text=f"🔄 Frequency: {exercise.get('frequency', 'N/A')}",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        frequency_label.grid(row=0, column=1, sticky="w")
        
        # YouTube section with video info and thumbnail
        youtube_frame = ctk.CTkFrame(card, fg_color="#1F2937", corner_radius=8)
        youtube_frame.grid(row=3, column=0, columnspan=3, pady=(0, 15), padx=15, sticky="ew")
        youtube_frame.grid_columnconfigure(1, weight=1)
        
        # Video thumbnail (left side)
        video_id = self.extract_video_id(exercise['youtube_link'])
        if video_id:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            thumbnail_label = ctk.CTkLabel(
                youtube_frame,
                text="🎬",
                font=ctk.CTkFont(size=20),
                text_color="#9CA3AF",
                width=80,
                height=45
            )
            thumbnail_label.grid(row=0, column=0, padx=10, pady=8)
            
            # Try to load actual thumbnail
            self.load_thumbnail(thumbnail_label, thumbnail_url)
            
            # Get video category
            video_category = self.get_video_category(video_id)
            video_title = f"📺 {video_category}: {video_id[:8]}..."
            channel_info = self.get_channel_info(video_id)
        else:
            video_title = "📺 YouTube Tutorial"
            channel_info = ""
        
        # Video info (middle)
        info_frame = ctk.CTkFrame(youtube_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=8)
        info_frame.grid_columnconfigure(0, weight=1)
        
        video_title_label = ctk.CTkLabel(
            info_frame,
            text=video_title,
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        video_title_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        # Channel info and video details
        if channel_info:
            channel_label = ctk.CTkLabel(
                info_frame,
                text=f"📺 {channel_info}",
                font=ctk.CTkFont(size=9),
                text_color="#6B7280"
            )
            channel_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
            
            # Video duration and popularity
            duration_text = self.get_video_duration(video_id)
            popularity_text = self.get_video_popularity(video_id)
            
            if duration_text:
                duration_label = ctk.CTkLabel(
                    info_frame,
                    text=f"⏱️ {duration_text}",
                    font=ctk.CTkFont(size=8),
                    text_color="#6B7280"
                )
                duration_label.grid(row=2, column=0, sticky="w", pady=(0, 2))
            
            if popularity_text:
                popularity_label = ctk.CTkLabel(
                    info_frame,
                    text=f"⭐ {popularity_text}",
                    font=ctk.CTkFont(size=8),
                    text_color="#F59E0B"
                )
                popularity_label.grid(row=3, column=0, sticky="w", pady=(0, 5))
        
        # YouTube buttons (right side)
        button_frame = ctk.CTkFrame(youtube_frame, fg_color="transparent")
        button_frame.grid(row=0, column=2, padx=(0, 10), pady=8)
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Watch button
        youtube_button = ctk.CTkButton(
            button_frame,
            text="▶️ Watch",
            command=lambda: self.open_youtube_video(exercise['youtube_link']),
            fg_color="#FF0000",
            hover_color="#CC0000",
            height=28,
            width=70
        )
        youtube_button.grid(row=0, column=0, padx=(0, 5))
        
        # Copy link button
        copy_button = ctk.CTkButton(
            button_frame,
            text="📋 Copy",
            command=lambda: self.copy_video_link(exercise['youtube_link']),
            fg_color="transparent",
            border_width=1,
            border_color="#6B7280",
            text_color="#6B7280",
            hover_color="#374151",
            height=28,
            width=50
        )
        copy_button.grid(row=0, column=1)
        
        return card

    def extract_video_id(self, url):
        """Extract video ID from YouTube URL."""
        try:
            if "youtube.com/watch?v=" in url:
                return url.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                return url.split("youtu.be/")[1].split("?")[0]
            else:
                return None
        except:
            return None

    def get_channel_info(self, video_id):
        """Get channel information based on video ID patterns."""
        # This is a simplified approach - in a real app you'd use YouTube API
        # For now, we'll return channel info based on common patterns
        try:
            # You can expand this with more channel mappings
            channel_mappings = {
                "2L916cqWXrI": "AskDoctorJo - Physical Therapy",
                "9hVzXI1K8Q8": "Bob & Brad - Physical Therapists",
                "2NOsE-VPpkE": "AskDoctorJo - Physical Therapy",
                "QhHJC8scOLY": "Bob & Brad - Physical Therapists",
                "Wvq7yqBdUcE": "AskDoctorJo - Physical Therapy",
                "1vuaaHosQvM": "Bob & Brad - Physical Therapists",
                "3VcgVdEjC84": "AskDoctorJo - Physical Therapy",
                "inpok4MKVLM": "Yoga With Adriene",
                "z6X5oEIg6Ak": "Boho Beautiful Yoga"
            }
            return channel_mappings.get(video_id, "YouTube Channel")
        except:
            return "YouTube Channel"

    def load_thumbnail(self, label, thumbnail_url):
        """Load YouTube thumbnail image."""
        try:
            import requests
            from io import BytesIO
            
            # Download thumbnail in background thread
            def download_thumbnail():
                try:
                    response = requests.get(thumbnail_url, timeout=5)
                    if response.status_code == 200:
                        img_data = BytesIO(response.content)
                        img = Image.open(img_data)
                        img.thumbnail((80, 45), Image.Resampling.LANCZOS)
                        
                        if self.is_running:
                            self.after(0, self.update_thumbnail, label, img)
                except Exception as e:
                    print(f"Error loading thumbnail: {e}")
            
            threading.Thread(target=download_thumbnail, daemon=True).start()
            
        except ImportError:
            # If requests is not available, keep the emoji
            pass
        except Exception as e:
            print(f"Error setting up thumbnail download: {e}")

    def update_thumbnail(self, label, img):
        """Update label with thumbnail image."""
        try:
            ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 45))
            label.configure(image=ctk_image, text="")
        except Exception as e:
            print(f"Error updating thumbnail: {e}")

    def get_video_duration(self, video_id):
        """Get estimated video duration based on video ID patterns."""
        # This is a simplified approach - in a real app you'd use YouTube API
        # For now, we'll return estimated durations based on common patterns
        try:
            # You can expand this with more duration mappings
            duration_mappings = {
                "2L916cqWXrI": "~15 min",  # AskDoctorJo - Back Pain Relief
                "9hVzXI1K8Q8": "~12 min",  # Bob & Brad - Lower Back Pain
                "2NOsE-VPpkE": "~18 min",  # AskDoctorJo - Neck Pain Relief
                "QhHJC8scOLY": "~10 min",  # Bob & Brad - Neck Pain Relief
                "Wvq7yqBdUcE": "~20 min",  # AskDoctorJo - Knee Pain Relief
                "1vuaaHosQvM": "~14 min",  # Bob & Brad - Knee Pain Relief
                "3VcgVdEjC84": "~16 min",  # AskDoctorJo - Shoulder Pain Relief
                "inpok4MKVLM": "~25 min",  # Yoga With Adriene - Stress Relief
                "z6X5oEIg6Ak": "~30 min"   # Boho Beautiful - Stress Relief
            }
            return duration_mappings.get(video_id, "~15 min")
        except:
            return "~15 min"

    def get_video_popularity(self, video_id):
        """Get video popularity rating based on video ID patterns."""
        try:
            # Popularity ratings based on view counts and quality
            popularity_mappings = {
                "2L916cqWXrI": "4.8/5 (2M+ views)",  # AskDoctorJo - Back Pain Relief
                "9hVzXI1K8Q8": "4.9/5 (1.5M+ views)",  # Bob & Brad - Lower Back Pain
                "2NOsE-VPpkE": "4.7/5 (1.8M+ views)",  # AskDoctorJo - Neck Pain Relief
                "QhHJC8scOLY": "4.8/5 (1.2M+ views)",  # Bob & Brad - Neck Pain Relief
                "Wvq7yqBdUcE": "4.9/5 (2.2M+ views)",  # AskDoctorJo - Knee Pain Relief
                "1vuaaHosQvM": "4.7/5 (1.6M+ views)",  # Bob & Brad - Knee Pain Relief
                "3VcgVdEjC84": "4.8/5 (1.9M+ views)",  # AskDoctorJo - Shoulder Pain Relief
                "inpok4MKVLM": "4.9/5 (5M+ views)",  # Yoga With Adriene - Stress Relief
                "z6X5oEIg6Ak": "4.8/5 (3M+ views)"   # Boho Beautiful - Stress Relief
            }
            return popularity_mappings.get(video_id, "4.5/5")
        except:
            return "4.5/5"

    def get_video_category(self, video_id):
        """Get video category based on video ID patterns."""
        try:
            # Video categories for better organization
            category_mappings = {
                "2L916cqWXrI": "Back Pain Relief",
                "9hVzXI1K8Q8": "Lower Back Pain",
                "2NOsE-VPpkE": "Neck Pain Relief",
                "QhHJC8scOLY": "Neck Pain Relief",
                "Wvq7yqBdUcE": "Knee Pain Relief",
                "1vuaaHosQvM": "Knee Pain Relief",
                "3VcgVdEjC84": "Shoulder Pain Relief",
                "inpok4MKVLM": "Stress Relief Yoga",
                "z6X5oEIg6Ak": "Stress Relief Yoga"
            }
            return category_mappings.get(video_id, "Exercise Tutorial")
        except:
            return "Exercise Tutorial"

    def copy_video_link(self, url):
        """Copy YouTube video link to clipboard."""
        try:
            import pyperclip
            pyperclip.copy(url)
            self.set_status("Video link copied to clipboard!", "green")
        except ImportError:
            try:
                # Fallback for Windows
                import subprocess
                subprocess.run(['clip'], input=url.encode(), check=True)
                self.set_status("Video link copied to clipboard!", "green")
            except:
                self.set_status("Could not copy link. Please copy manually.", "red")
        except Exception as e:
            self.set_status(f"Error copying link: {e}", "red")

    def open_youtube_video(self, url):
        """Open YouTube video in default browser."""
        try:
            import webbrowser
            webbrowser.open(url)
            self.set_status("Opening YouTube tutorial in browser...", "blue")
        except Exception as e:
            self.set_status(f"Error opening video: {e}", "red")

    def display_exercise_error(self, error_message):
        """Display error message when exercise recommendations fail."""
        if not self.is_running:
            return
        
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()
        
        error_label = ctk.CTkLabel(
            self.results_scroll_frame,
            text=f"❌ {error_message}",
            font=ctk.CTkFont(size=14),
            text_color="#EF4444",
            wraplength=500
        )
        error_label.pack(pady=50)
        
        # Add retry button
        retry_button = ctk.CTkButton(
            self.results_scroll_frame,
            text="🔄 Try Again",
            command=self.get_exercise_recommendations,
            fg_color="#3B82F6",
            hover_color="#60A5FA"
        )
        retry_button.pack(pady=20)

    def enable_recommendations_button(self):
        """Re-enable the recommendations button."""
        if not self.is_running:
            return
        
        self.get_recommendations_button.configure(state="normal", text="Get Exercise Recommendations")

    def save_exercise_recommendation(self, recommendations, pain_description):
        """Save exercise recommendation to user's history."""
        if not self.is_running:
            return
        
        try:
            # Load existing history
            history_file = "exercise_history.json"
            history = []
            
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            
            # Add new recommendation with timestamp
            history_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "pain_description": pain_description,
                "recommendations": recommendations
            }
            
            history.append(history_entry)
            
            # Keep only last 20 entries
            if len(history) > 20:
                history = history[-20:]
            
            # Save updated history
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
            
            # Refresh history display
            self.load_exercise_history()
            
        except Exception as e:
            print(f"Error saving exercise history: {e}")

    def load_exercise_history(self):
        """Load and display exercise history."""
        if not self.is_running:
            return
        
        try:
            # Clear existing history
            for widget in self.history_scroll_frame.winfo_children():
                widget.destroy()
            
            # Load history from file
            history_file = "exercise_history.json"
            if not os.path.exists(history_file):
                no_history_label = ctk.CTkLabel(
                    self.history_scroll_frame,
                    text="No exercise history yet. Get your first recommendations above!",
                    font=ctk.CTkFont(size=12),
                    text_color="#9CA3AF"
                )
                no_history_label.pack(pady=20)
                return
            
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            if not history:
                no_history_label = ctk.CTkLabel(
                    self.history_scroll_frame,
                    text="No exercise history yet. Get your first recommendations above!",
                    font=ctk.CTkFont(size=12),
                    text_color="#9CA3AF"
                )
                no_history_label.pack(pady=20)
                return
            
            # Display history entries (most recent first)
            for entry in reversed(history[-5:]):  # Show last 5 entries
                history_card = self.create_history_card(entry)
                history_card.pack(fill="x", pady=(0, 10), padx=5)
                
        except Exception as e:
            print(f"Error loading exercise history: {e}")
            error_label = ctk.CTkLabel(
                self.history_scroll_frame,
                text="Error loading exercise history.",
                font=ctk.CTkFont(size=12),
                text_color="#EF4444"
            )
            error_label.pack(pady=20)

    def create_history_card(self, history_entry):
        """Create a card widget for displaying history entry."""
        card = ctk.CTkFrame(self.history_scroll_frame, corner_radius=8, fg_color="#374151")
        card.grid_columnconfigure(0, weight=1)
        
        # Timestamp and pain description
        timestamp = datetime.datetime.fromisoformat(history_entry['timestamp']).strftime("%b %d, %Y at %I:%M %p")
        
        time_label = ctk.CTkLabel(
            card,
            text=f"📅 {timestamp}",
            font=ctk.CTkFont(size=10),
            text_color="#9CA3AF"
        )
        time_label.grid(row=0, column=0, sticky="w", padx=10, pady=(8, 2))
        
        pain_label = ctk.CTkLabel(
            card,
            text=f"🎯 {history_entry['pain_description'][:50]}{'...' if len(history_entry['pain_description']) > 50 else ''}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FFFFFF"
        )
        pain_label.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        
        # View details button
        view_button = ctk.CTkButton(
            card,
            text="View Details",
            command=lambda: self.view_history_details(history_entry),
            fg_color="transparent",
            border_width=1,
            border_color="#3B82F6",
            text_color="#3B82F6",
            hover_color="#1F2937",
            height=24,
            width=80
        )
        view_button.grid(row=0, column=1, rowspan=2, padx=10, pady=8)
        
        return card

    def view_history_details(self, history_entry):
        """View detailed history entry in a popup window."""
        if not self.is_running:
            return
        
        # Create popup window
        popup = ctk.CTkToplevel(self)
        popup.title("Exercise Recommendation Details")
        popup.geometry("600x500")
        popup.transient(self)
        popup.grab_set()
        
        # Make popup scrollable
        scroll_frame = ctk.CTkScrollableFrame(popup)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Display timestamp
        timestamp = datetime.datetime.fromisoformat(history_entry['timestamp']).strftime("%B %d, %Y at %I:%M %p")
        time_label = ctk.CTkLabel(
            scroll_frame,
            text=f"📅 {timestamp}",
            font=ctk.CTkFont(size=14),
            text_color="#9CA3AF"
        )
        time_label.pack(pady=(0, 10))
        
        # Display pain description
        pain_label = ctk.CTkLabel(
            scroll_frame,
            text=f"🎯 Pain/Discomfort: {history_entry['pain_description']}",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF",
            wraplength=500
        )
        pain_label.pack(pady=(0, 20))
        
        # Display recommendations
        recommendations = history_entry['recommendations']
        for i, exercise in enumerate(recommendations['exercise_suggestions']):
            exercise_card = self.create_exercise_card(exercise, i + 1)
            exercise_card.pack(fill="x", pady=(0, 15), padx=5)
        
        # Display notes if available
        if recommendations.get('notes'):
            notes_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color="#374151")
            notes_frame.pack(fill="x", pady=(10, 0), padx=5)
            
            notes_label = ctk.CTkLabel(
                notes_frame,
                text=f"💡 {recommendations['notes']}",
                font=ctk.CTkFont(size=12),
                text_color="#D1D5DB",
                wraplength=500,
                justify="left"
            )
            notes_label.pack(padx=15, pady=15)

            # ===================================================================
    # ✨ NEW TAB: Doctor Consultation
    # ===================================================================
    def create_doctor_consultation_tab(self, tab):
        if not self.is_running: return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # --- Header and Search Area ---
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(header_frame, text="👨‍⚕️ Find & Book a Doctor", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        
        # Search Entry for city
        self.doctor_city_entry = ctk.CTkEntry(header_frame, placeholder_text="Enter your city (e.g., Jodhpur)")
        self.doctor_city_entry.grid(row=1, column=0, pady=(10, 0), sticky="ew")
        
        # Dropdown for specialty
        specialties = ["All Specialties", "Cardiologist", "Dermatologist", "General Physician", "Neurologist", "Orthopedist", "Pediatrician"]
        self.doctor_specialty_var = ctk.StringVar(value="All Specialties")
        specialty_menu = ctk.CTkOptionMenu(header_frame, variable=self.doctor_specialty_var, values=specialties)
        specialty_menu.grid(row=1, column=1, padx=10, pady=(10, 0), sticky="ew")

        search_button = ctk.CTkButton(header_frame, text="🔍 Search Doctors", command=self.search_doctors)
        search_button.grid(row=1, column=2, pady=(10, 0), sticky="ew")

        # --- Main Content Area for Doctor Listings ---
        self.doctor_results_frame = ctk.CTkScrollableFrame(tab)
        self.doctor_results_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.doctor_results_frame.grid_columnconfigure(0, weight=1)

        # Load initial doctors (or a placeholder)
        self.search_doctors(initial_load=True)

    def search_doctors(self, initial_load=False):
        """Filters and displays doctors based on search criteria."""
        for widget in self.doctor_results_frame.winfo_children():
            widget.destroy()

        city = self.doctor_city_entry.get().strip().lower() if hasattr(self, 'doctor_city_entry') else ""
        specialty = self.doctor_specialty_var.get() if hasattr(self, 'doctor_specialty_var') else "All Specialties"

        # In a real app, this data would come from a database or API
        all_doctors = [
            {"name": "Dr. Anjali Sharma", "specialty": "Cardiologist", "city": "jodhpur", "experience": "15 Years", "availability": ["Mon", "Wed", "Fri"], "consultation": "Online & In-Clinic"},
            {"name": "Dr. Vikram Singh", "specialty": "Orthopedist", "city": "jodhpur", "experience": "20 Years", "availability": ["Tue", "Thu"], "consultation": "In-Clinic Only"},
            {"name": "Dr. Priya Gupta", "specialty": "Dermatologist", "city": "jaipur", "experience": "8 Years", "availability": ["Mon-Fri"], "consultation": "Online Only"},
            {"name": "Dr. Rahul Verma", "specialty": "General Physician", "city": "jodhpur", "experience": "10 Years", "availability": ["Mon-Sat"], "consultation": "Online & In-Clinic"},
            {"name": "Dr. Sunita Agarwal", "specialty": "Pediatrician", "city": "jaipur", "experience": "12 Years", "availability": ["Mon", "Tue", "Thu", "Fri"], "consultation": "In-Clinic Only"},
        ]

        # Filter logic
        filtered_doctors = []
        for doctor in all_doctors:
            city_match = not city or city in doctor["city"]
            specialty_match = specialty == "All Specialties" or specialty == doctor["specialty"]
            if city_match and specialty_match:
                filtered_doctors.append(doctor)

        if initial_load:
            ctk.CTkLabel(self.doctor_results_frame, text="Enter a city and select a specialty to find doctors near you.", 
                         font=ctk.CTkFont(size=16), text_color="gray").pack(pady=50)
            return

        if not filtered_doctors:
            ctk.CTkLabel(self.doctor_results_frame, text="No doctors found matching your criteria. Please try another search.", 
                         font=ctk.CTkFont(size=16), text_color="gray").pack(pady=50)
        else:
            for doctor in filtered_doctors:
                card = self.create_doctor_card(doctor)
                card.pack(fill="x", padx=10, pady=10)
    
    def create_doctor_card(self, doctor_info):
        """Creates a visual card for a single doctor."""
        card = ctk.CTkFrame(self.doctor_results_frame, corner_radius=15, border_width=1, border_color="#444444")
        card.grid_columnconfigure(1, weight=1)

        # Placeholder for doctor's photo
        photo_frame = ctk.CTkFrame(card, fg_color="#3B82F6", width=80, height=80, corner_radius=10)
        photo_frame.grid(row=0, column=0, rowspan=3, padx=15, pady=15)
        ctk.CTkLabel(photo_frame, text="👨‍⚕️", font=ctk.CTkFont(size=40)).pack(expand=True)
        
        # Doctor's details
        name_label = ctk.CTkLabel(card, text=doctor_info["name"], font=ctk.CTkFont(size=18, weight="bold"))
        name_label.grid(row=0, column=1, sticky="sw", padx=10, pady=(10, 0))

        specialty_label = ctk.CTkLabel(card, text=f"{doctor_info['specialty']} • {doctor_info['experience']} Experience", 
                                       font=ctk.CTkFont(size=12), text_color="gray")
        specialty_label.grid(row=1, column=1, sticky="nw", padx=10)

        # Consultation and Availability
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=2, column=1, sticky="ew", padx=10, pady=(5, 10))

        consultation_type = doctor_info["consultation"]
        consult_color = "#10B981" if "Online" in consultation_type else "#F59E0B"
        ctk.CTkLabel(info_frame, text=f"Consultation: {consultation_type}", fg_color=consult_color, corner_radius=5,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        ctk.CTkLabel(info_frame, text=f"Available: {', '.join(doctor_info['availability'])}", 
                     font=ctk.CTkFont(size=11), text_color="gray").pack(side="left", padx=10)
        
        # Booking Buttons
        button_frame = ctk.CTkFrame(card, fg_color="transparent")
        button_frame.grid(row=0, column=2, rowspan=3, padx=15)

        book_clinic_button = ctk.CTkButton(button_frame, text="Book In-Clinic", height=35, command=lambda d=doctor_info: self.book_appointment(d, "In-Clinic"))
        book_clinic_button.pack(pady=5)

        book_online_button = ctk.CTkButton(button_frame, text="Book Online", height=35, command=lambda d=doctor_info: self.book_appointment(d, "Online"), 
                                           fg_color="#10B981", hover_color="#059669")
        book_online_button.pack(pady=5)
        
        if "Online" not in consultation_type:
            book_online_button.configure(state="disabled")
        if "In-Clinic" not in consultation_type:
            book_clinic_button.configure(state="disabled")

        return card

    def book_appointment(self, doctor_info, appt_type):
        """Placeholder function to handle the booking action."""
        # In a real app, this would open a calendar, handle payments, etc.
        message = f"Booking an '{appt_type}' appointment with {doctor_info['name']}..."
        self.set_status(message, "green")
        
        # Show a confirmation dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Appointment Booking")
        dialog.geometry("350x150")
        dialog.transient(self)
        dialog.grab_set()

        label = ctk.CTkLabel(dialog, text=f"{message}\n\n(This is a demo. No actual booking will be made.)", wraplength=300)
        label.pack(pady=20, padx=20)
        
        ok_button = ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100)
        ok_button.pack(pady=10)

# ===================================================================
    # ✨ NEW TAB: Medicine Suggestions
    # ===================================================================
    def create_medicine_suggestions_tab(self, tab):
        if not self.is_running: return
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # --- Header and Input ---
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="💊 AI Medicine Suggestions", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(header_frame, text="Describe a symptom or condition to get AI-powered suggestions. (For informational purposes only)", text_color="gray").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.symptom_entry = ctk.CTkEntry(header_frame, placeholder_text="e.g., 'Headache and sinus pressure', 'Indigestion', 'Joint pain'")
        self.symptom_entry.grid(row=2, column=0, sticky="ew")

        self.suggestion_button = ctk.CTkButton(header_frame, text="Get Suggestions", command=self.get_medicine_suggestions)
        self.suggestion_button.grid(row=2, column=1, padx=(10, 0))

        # --- Results Display Area ---
        results_frame = ctk.CTkFrame(tab, fg_color="transparent")
        results_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        results_frame.grid_columnconfigure((0, 1), weight=1)
        results_frame.grid_rowconfigure(1, weight=1)
        
        # --- Allopathic Suggestions ---
        ctk.CTkLabel(results_frame, text="Modern Medicine (Allopathy)", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=10, sticky="w")
        self.allopathic_textbox = ctk.CTkTextbox(results_frame, wrap="word", state="disabled", corner_radius=10)
        self.allopathic_textbox.grid(row=1, column=0, padx=(0, 10), sticky="nsew")
        
        # --- Ayurvedic Suggestions ---
        ctk.CTkLabel(results_frame, text="Traditional Remedies (Ayurveda)", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=1, padx=10, sticky="w")
        self.ayurvedic_textbox = ctk.CTkTextbox(results_frame, wrap="word", state="disabled", corner_radius=10)
        self.ayurvedic_textbox.grid(row=1, column=1, padx=(10, 0), sticky="nsew")

    def get_medicine_suggestions(self):
        symptom = self.symptom_entry.get().strip()
        if not symptom:
            self.set_status("Please enter a symptom or condition.", "red")
            return
        
        self.set_status(f"Getting AI suggestions for '{symptom}'...", "blue")
        self.suggestion_button.configure(state="disabled")
        
        # Clear previous results
        self.allopathic_textbox.configure(state="normal")
        self.ayurvedic_textbox.configure(state="normal")
        self.allopathic_textbox.delete("1.0", "end")
        self.ayurvedic_textbox.delete("1.0", "end")
        self.allopathic_textbox.configure(state="disabled")
        self.ayurvedic_textbox.configure(state="disabled")
        
        threading.Thread(target=self.run_medicine_search_in_thread, args=(symptom,), daemon=True).start()

    def run_medicine_search_in_thread(self, symptom):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Act as a knowledgeable health advisor. The user is asking for suggestions for the following symptom/condition: "{symptom}".

            Your task is to provide:
            1.  A list of 2-3 common over-the-counter Allopathic (Modern Medicine) suggestions.
            2.  A list of 2-3 common Ayurvedic (Traditional Indian) remedies or supplements.
            3.  For each suggestion, briefly describe its common use and any important precautions.
            4.  Include a very clear and prominent disclaimer at the end.

            Respond ONLY with a valid JSON object in the following format. Do not include any text before or after the JSON object.
            ```json
            {{
              "allopathic": [
                {{
                  "name": "string (e.g., Paracetamol)",
                  "use": "string (e.g., For pain and fever relief.)",
                  "notes": "string (e.g., Do not exceed recommended dosage.)"
                }}
              ],
              "ayurvedic": [
                {{
                  "name": "string (e.g., Turmeric (Haldi) Milk)",
                  "use": "string (e.g., Known for its anti-inflammatory properties.)",
                  "notes": "string (e.g., Best consumed warm before bedtime.)"
                }}
              ],
              "disclaimer": "This is AI-generated information and not a substitute for professional medical advice. Always consult a qualified doctor or healthcare provider before starting any new treatment."
            }}
            ```
            """
            response = model.generate_content(prompt)
            suggestions = self._safe_json_loads(response.text)

            if self.is_running:
                self.after(0, self.display_medicine_suggestions, suggestions)

        except Exception as e:
            print(f"Error fetching medicine suggestions from AI: {e}")
            if self.is_running:
                self.after(0, self.set_status, f"An error occurred: {e}", "red")

    def display_medicine_suggestions(self, suggestions):
        if not suggestions:
            self.set_status("Could not retrieve suggestions. Please try again.", "red")
            self.suggestion_button.configure(state="normal")
            return

        # --- Display Allopathic Suggestions ---
        self.allopathic_textbox.configure(state="normal")
        self.allopathic_textbox.delete("1.0", "end")
        allopathic_meds = suggestions.get("allopathic", [])
        if allopathic_meds:
            for med in allopathic_meds:
                self.allopathic_textbox.insert("end", f"{med['name']}\n", "header")
                self.allopathic_textbox.insert("end", f"Use: {med['use']}\n", "text")
                self.allopathic_textbox.insert("end", f"Note: {med['notes']}\n\n", "note")
        else:
            self.allopathic_textbox.insert("end", "No specific suggestions found.", "text")
        
        # --- Display Ayurvedic Suggestions ---
        self.ayurvedic_textbox.configure(state="normal")
        self.ayurvedic_textbox.delete("1.0", "end")
        ayurvedic_remedies = suggestions.get("ayurvedic", [])
        if ayurvedic_remedies:
            for remedy in ayurvedic_remedies:
                self.ayurvedic_textbox.insert("end", f"{remedy['name']}\n", "header")
                self.ayurvedic_textbox.insert("end", f"Use: {remedy['use']}\n", "text")
                self.ayurvedic_textbox.insert("end", f"Note: {remedy['notes']}\n\n", "note")
        else:
            self.ayurvedic_textbox.insert("end", "No specific suggestions found.", "text")

        # --- Display Disclaimer ---
        disclaimer = suggestions.get("disclaimer", "Always consult a doctor before taking any medication.")
        disclaimer_text = f"\n\n⚠️ Disclaimer: {disclaimer}"
        self.allopathic_textbox.insert("end", disclaimer_text, "disclaimer")
        self.ayurvedic_textbox.insert("end", disclaimer_text, "disclaimer")
        
        # --- Configure Textbox Styling ---
        for textbox in [self.allopathic_textbox, self.ayurvedic_textbox]:
            textbox.tag_config("header", font=ctk.CTkFont(size=14, weight="bold"), foreground="#3498db")
            textbox.tag_config("text", font=ctk.CTkFont(size=12))
            textbox.tag_config("note", font=ctk.CTkFont(size=11, slant="italic"), foreground="gray")
            textbox.tag_config("disclaimer", font=ctk.CTkFont(size=10, weight="bold"), foreground="#e74c3c")
            textbox.configure(state="disabled")

        self.suggestion_button.configure(state="normal")
        self.set_status("Suggestions generated successfully.", "green")
        
if __name__ == "__main__":
    app = NutriScanApp()  # ✅ Must use your class, not tk.Tk()
    app.mainloop()