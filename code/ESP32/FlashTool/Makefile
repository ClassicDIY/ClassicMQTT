
build: 
	@echo "creating Stand Alone exe"
	pyinstaller --console --onefile --name=flasher --distpath=.\.. --icon=ESP32-chip-icon.ico flasher.py

clean: 
	@echo "cleaning..."
	rmdir /Q /S __pycache__
	rmdir /Q /S build




