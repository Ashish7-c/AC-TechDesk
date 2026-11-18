
# AC-TechDesk — IT Help Desk Management System

AC-TechDesk is a full-stack IT support ticket management
application developed using Python, Flask, SQLite, HTML,
and CSS.

The application allows employees to submit IT support
requests, administrators to assign tickets, and technicians
to troubleshoot and resolve issues.

## 🌐 Live Application

**Live Demo:** https://ac-techdesk.onrender.com

**Source Code:** https://github.com/Ashish7-c/AC-TechDesk

**Deployment:** Render (Python, Flask, Gunicorn)

> **Note:** This is a portfolio demonstration.
> It uses temporary SQLite storage on Render Free.
> Test accounts and tickets may reset after a service
> restart or redeployment.

## Features

### Support Ticket Management
- Create IT support tickets
- Assign ticket priorities
- Categorize IT issues
- Track ticket status
- Assign tickets to registered technicians
- Record troubleshooting and resolution notes
- View ticket activity history
- Search and filter support requests

### Authentication and Authorization
- Secure password hashing
- Login and logout
- CSRF protection
- Role-based access control
- Admin, Technician, and Employee roles

### Admin Features
- View all support tickets
- Create Technician and Employee accounts
- Activate or deactivate user accounts
- Assign tickets to technicians
- View reports and analytics

### Technician Features
- View assigned support tickets
- Update ticket status
- Document troubleshooting steps

### Employee Features
- Submit support tickets
- Track submitted requests
- View ticket progress

### Reports and Analytics
- Total ticket statistics
- Tickets by status
- Tickets by priority
- Tickets by category
- Technician workload overview

### Knowledge Base
- Common IT troubleshooting guides
- Wi-Fi and networking support
- Email troubleshooting
- Printer troubleshooting
- Windows login assistance

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web application framework |
| SQLite | Database |
| HTML5 | Page structure |
| CSS3 | Styling |
| Jinja2 | Dynamic templates |
| Flask-Login | User authentication |
| Flask-WTF | CSRF protection |
| Git | Version control |

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR-USERNAME/AC-TechDesk.git
cd AC-TechDesk
```

Replace YOUR-USERNAME with the actual GitHub username
after the repository is created.

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the environment

For Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize the database

Run the Flask application once:

```bash
python app.py
```

Stop the server with Ctrl+C.

### 6. Create the administrator account

```bash
python create_admin.py
```

Follow the script's instructions to create the Admin account.

### 7. Start the application

```bash
python app.py
```

Open:

http://127.0.0.1:5000

## User Roles

| Feature | Admin | Technician | Employee |
|---|---|---|---|
| View all tickets | Yes | No | No |
| View assigned tickets | Yes | Yes | No |
| Submit tickets | Yes | Yes | Yes |
| View own requests | Yes | No | Yes |
| Update ticket status | Yes | Yes | No |
| Assign technicians | Yes | No | No |
| Manage users | Yes | No | No |
| View analytics | Yes | No | No |

## Security

The application includes:

- Password hashing
- Role-based authorization
- CSRF protection
- Protected Flask routes
- Account activation and deactivation

This project is currently intended for local development
and portfolio demonstration.

Additional security review and production configuration
are required before using real organizational data.

## Screenshots

Screenshots of the following pages will be added:

- Admin Dashboard
- Ticket Details
- User Management
- Reports and Analytics
- Login Page


## Project Status

✅ Core application functionality completed  
✅ Role-based authentication implemented  
✅ Ticket creation and assignment tested  
✅ Technician resolution workflow tested  
✅ Administrator reports and user management tested  
✅ Deployed successfully on Render  

**Live Website:** https://ac-techdesk.onrender.com


## Future Improvements

- Password reset functionality
- Email notifications
- Ticket comments
- SLA tracking
- Export reports to CSV
- Secure cloud deployment

## Author

Developed as a full-stack Python and IT Support
portfolio project.

## License

No license has been selected yet.
```
