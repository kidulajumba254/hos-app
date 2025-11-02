  ELD HOS Planner — Full-Stack App (Django + React)

A full-stack web application that generates FMCSA Hours-of-Service (HOS)-compliant driver logs and visual route maps.  
Built with **Django REST Framework** for the backend and **React + Leaflet** for the frontend.


 Features

- **Trip input form** — takes Current, Pickup, and Drop-off locations.
- **Route mapping** — displays a driving route using the OSRM API (OpenStreetMap).
- **HOS compliance logic** — applies U.S. FMCSA 70-hour / 8-day property-carrying driver rules.
- **Daily Log Sheet generator** — draws ELD log bars on a digital canvas.
- **REST API** — `/api/plan-route/` endpoint calculates and returns activities with time stamps.
- **CORS-enabled communication** between Django and React.


  Tech Stack
 Layer  Technology 

 Frontend - React, Leaflet, Leaflet-Routing-Machine, HTML Canvas 
 Backend - Django 4+, Django REST Framework, django-cors-headers 
 Language  -Python 3.12, JavaScript (ES6) 
 Map Data - OpenStreetMap + OSRM public routing service 
 Hosting - Backend → Render / Railway; Frontend → Vercel 


  Local Setup

 1️ Clone the repo
bash
git clone (https://github.com/kidulajumba254/hos-app.git)
cd hos-app


Commmands 
**frontend**- npm start
**Backend**-python manage.py runserver ,but first activate the virtual environment- venv\Scripts\activate



*This project is just a glimpse or a snippet of what is supposed to be deployed fully*"# hos-app" 
