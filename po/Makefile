# po/Makefile — disk_cleaner gettext build
#
# Hedefler:
#   make pot      → messages.pot (kaynak kod'dan xgettext extract)
#   make update   → tüm dillere msgmerge (mevcut çevirileri korur)
#   make compile  → tüm .po dosyalarını .mo'ya derler → ../disk_cleaner/locale/
#   make all      → pot + update + compile
#
# Yeni dil eklemek için:
#   cd po && msginit -i messages.pot -l <lang> -o <lang>.po

DOMAIN     := disk_cleaner
POT        := messages.pot
LANGS      := $(patsubst %.po,%,$(wildcard *.po))
LOCALEDIR  := ../disk_cleaner/locale
SOURCES    := $(shell find ../disk_cleaner -name '*.py' | sort)

.PHONY: all pot update compile clean check

all: pot update compile

pot:
	xgettext \
		--language=Python \
		--from-code=UTF-8 \
		--keyword=_ --keyword=ngettext:1,2 \
		--package-name=$(DOMAIN) \
		--copyright-holder='Codechu' \
		--msgid-bugs-address='info@codechu.com' \
		--output=$(POT) \
		--add-comments=Translators \
		--sort-output \
		$(SOURCES)
	@echo "→ $(POT) yenilendi ($(words $(SOURCES)) kaynak dosya)"

update:
	@for lang in $(LANGS); do \
		echo "→ $$lang.po güncelleniyor..."; \
		msgmerge --update --backup=none --quiet $$lang.po $(POT); \
	done

compile:
	@for lang in $(LANGS); do \
		mkdir -p $(LOCALEDIR)/$$lang/LC_MESSAGES; \
		msgfmt --check --output=$(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).mo $$lang.po; \
		echo "→ $(LOCALEDIR)/$$lang/LC_MESSAGES/$(DOMAIN).mo"; \
	done

check:
	@for lang in $(LANGS); do \
		echo "── $$lang.po ──"; \
		msgfmt --statistics --output=/dev/null $$lang.po; \
	done

clean:
	rm -f $(POT)
	rm -rf $(LOCALEDIR)
