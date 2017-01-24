# Inventory_System
Design project, ECE 458

# Requirements
http://people.duke.edu/~tkb13/courses/ece458/ev1.pdf

# Setup and Installation

Clone.
```
git clone https://github.com/nbv3/inventory_system
cd inventory_system
```

Create/activate new Python 3 ```virtualenv```.
```
python3 -m venv env
source env/bin/activate
```

Install ```pip``` and ```npm``` packages.
```
pip install --upgrade pip
pip install -r requirements.txt
npm install
```

Compile JSX and place in Django application's ```static``` directory via ```webpack``` (see package.json).
```
npm run build
```

Start Django server.
```
python kipventory/manage.py runserver
```