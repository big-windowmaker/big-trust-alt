# Big Trust Alt — build, test and install (PREFIX=/usr DESTDIR=… for packaging).
PREFIX ?= /usr
DESTDIR ?=
APPDIR = $(PREFIX)/share/big-trust-alt
PYTHON ?= python3
APP_ID = io.github.big_windowmaker.BigTrustAlt
LANGS = pt_BR

.PHONY: all build check lint install uninstall clean

all: build

build:
	@mkdir -p build/locale
	@for l in $(LANGS); do \
		mkdir -p build/locale/$$l/LC_MESSAGES; \
		msgfmt --check -o build/locale/$$l/LC_MESSAGES/big-trust-alt.mo po/$$l.po || exit 1; \
	done

check: build
	$(PYTHON) tools/validate_catalog.py
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m pytest -q -p no:cacheprovider tests

lint:
	ruff check src tests tools

install: build
	install -d $(DESTDIR)$(APPDIR)
	cp -r src/big_trust_alt $(DESTDIR)$(APPDIR)/
	find $(DESTDIR)$(APPDIR) -name '__pycache__' -prune -exec rm -rf {} +
	install -d $(DESTDIR)$(APPDIR)/app-db/catalog $(DESTDIR)$(APPDIR)/schemas
	install -m644 data/app-db/catalog/*.json $(DESTDIR)$(APPDIR)/app-db/catalog/
	install -m644 data/schemas/*.json $(DESTDIR)$(APPDIR)/schemas/
	install -Dm755 bin/big-trust-alt $(DESTDIR)$(PREFIX)/bin/big-trust-alt
	install -Dm644 data/desktop/$(APP_ID).desktop $(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop
	install -Dm644 data/desktop/$(APP_ID).metainfo.xml $(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	install -Dm644 data/icons/hicolor/scalable/apps/$(APP_ID).svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	install -Dm644 data/icons/hicolor/symbolic/apps/$(APP_ID)-symbolic.svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/symbolic/apps/$(APP_ID)-symbolic.svg
	@for l in $(LANGS); do \
		install -Dm644 build/locale/$$l/LC_MESSAGES/big-trust-alt.mo \
			$(DESTDIR)$(PREFIX)/share/locale/$$l/LC_MESSAGES/big-trust-alt.mo; \
	done

uninstall:
	rm -rf $(DESTDIR)$(APPDIR)
	rm -f $(DESTDIR)$(PREFIX)/bin/big-trust-alt \
		$(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop \
		$(DESTDIR)$(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/symbolic/apps/$(APP_ID)-symbolic.svg
	@for l in $(LANGS); do rm -f $(DESTDIR)$(PREFIX)/share/locale/$$l/LC_MESSAGES/big-trust-alt.mo; done

clean:
	rm -rf build
