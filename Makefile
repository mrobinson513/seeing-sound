run:
	@python analyze.py

gui:
	@poetry run run_gui

create:
	@poetry run pyinstaller --noconfirm --clean seeing-sound.spec
