# 🍔 WhatsApp Order Automation & Kitchen Display System (KDS)

![Python](https://img.shields.io/badge/Backend-Python%20%7C%20Flask-blue) ![WhatsApp API](https://img.shields.io/badge/Integration-WhatsApp%20Business%20Cloud-green) ![Real-Time](https://img.shields.io/badge/Feature-Socket.IO%20RealTime-red) ![Database](https://img.shields.io/badge/Database-PostgreSQL-blue)

> **Project Context:** A full-stack automated ordering solution developed for a restaurant (ODTÜ Maydanoz Döner). It bridges the gap between customer orders on WhatsApp and kitchen operations via a real-time web dashboard.

## 🎯 Project Overview
This system eliminates manual order taking by transforming WhatsApp into a fully automated ordering channel. It handles the entire flow from product selection to kitchen notification without human intervention.

**Key capabilities:**
* **Customers:** Order food, apply coupons, and customize items directly inside WhatsApp.
* **Kitchen/Staff:** Receive orders instantly on a live dashboard with audio alerts (no page refresh required).
* **Management:** Update menus, prices, and discount coupons dynamically via an admin panel.

## 🏗️ System Architecture

The project consists of two main micro-services interacting with a PostgreSQL database:

1.  **WhatsApp Webhook (`api.py`):**
    * Handles incoming messages from WhatsApp Cloud API.
    * Manages **User Session State** (Greeting -> Menu Selection -> Cart -> Confirmation).
    * Processes business logic like **Coupon Validation** and Cart Calculation.
    * Uses `psycopg2` for high-performance raw SQL queries.

2.  **Admin Dashboard & KDS (`app.py`):**
    * **Real-Time Communication:** Uses **Flask-SocketIO** to push new orders to the frontend instantly.
    * **ORM Layer:** Uses **SQLAlchemy** for complex admin operations (Menu CRUD, Coupon Management).
    * **Frontend:** HTML/CSS/JS interfaces for the Kitchen Display System (`home.html`) and Menu Manager (`menu.html`).

## 🚀 Key Features

### 📱 Customer Side (WhatsApp Bot)
* **Interactive Flow:** Uses WhatsApp "Interactive Messages" (Buttons & List Messages) for a smooth UX.
* **State Management:** Tracks where the user is in the ordering process (Redis-like logic implemented via DB).
* **Dynamic Cart:** Users can add multiple items, view the cart, and confirm orders.
* **Discount System:** Real-time validation of coupon codes.

### 💻 Business Side (Web Dashboard)
* **Live Order Feed:** Incoming orders appear instantly with a "Ding" sound effect.
* **Status Tracking:** Staff can mark orders as "Preparing" or "Delivered".
* **Menu Engineering:**
    * Add/Remove Products.
    * Update Prices instantly.
    * Create usage-limited Coupons (e.g., "First 50 users get 10% off").

## 🛠️ Technologies & Tools

* **Backend:** Python, Flask, Flask-SocketIO, SQLAlchemy.
* **Database:** PostgreSQL (Hosted on DigitalOcean).
* **API:** Meta (Facebook) WhatsApp Cloud API.
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (Socket.client).
* **Deployment:** (Mention where you deployed it, e.g., Heroku, DigitalOcean, or Localhost).

## 📸 Screenshots

| Kitchen Dashboard (Live) | WhatsApp Order Flow | Menu Management |
|:---:|:---:|:---:|
| ![Dashboard](screenshots/dashboard.png) | ![WhatsApp](screenshots/whatsapp_flow.png) | ![Menu](screenshots/admin.png) |
*(Placeholders for actual screenshots)*

## 🧩 Database Schema (Simplified)
* `orders`: Stores order details, status, and timestamps.
* `customers`: Manages user phone numbers and profiles.
* `products`: Menu items with categories and prices.
* `coupons`: Discount codes with usage limits and logic.

---
*Developed by Fatih Dallı*
