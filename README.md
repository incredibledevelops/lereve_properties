# Le Rêve Properties — Luxury Stays Platform

A full-featured luxury property booking platform built with **Flask + MongoDB + Paystack**.
Currency: **Ghana Cedis (GHS / ₵)**.

## ✨ Features

### Public Site
- Curated estate listings with AJAX filtering (category, price, location)
- Quick-view modal with gallery
- Wishlist (auth required)
- Confidential inquiry form → email + database
- Estate owner onboarding form
- Private journal newsletter subscription
- Reviews (moderated)
- SEO: `robots.txt`, `sitemap.xml`
- Legal pages: Privacy Policy & Terms of Privilege

### Client Portal (`/client`)
- Dashboard with upcoming stays, stats, activity
- Bookings with filters (all / upcoming / past)
- **Paystack checkout** for pending bookings (GHS)
- Wishlist management
- Inquiry tracking
- Concierge chat (real-time auto-reply placeholder)
- Profile + password change
- Stay preferences + communication preferences

### Super Admin (`/super-admin`)
- Dashboard with KPI cards + recent inquiries
- Full property CRUD
- Owner submission review (approve / reject / delete)
- Inquiry pipeline management
- Review moderation
- Journal subscriber management
- Booking oversight with status updates
- Site settings + data export / reset

## 🧱 Tech Stack
- **Flask 3.0** with Blueprints
- **MongoDB** via `Flask-PyMongo`
- **Flask-Login** for authentication
- **Flask-WTF** for CSRF-safe forms
- **Paystack** for GHS payments
- **Tailwind CDN** + custom Cormorant Garamond / Inter typography

## 🚀 Getting Started

### 1. Clone & create virtual env
```bash
git clone <repo>
cd lereve-properties
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate