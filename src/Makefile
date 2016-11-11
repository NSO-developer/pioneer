all:	fxs py xsls

# Include standard NCS examples build definitions and rules
include $(NCS_DIR)/src/ncs/build/include.ncs.mk

SRC = $(wildcard yang/*.yang)
FXS = $(SRC:yang/%.yang=../load-dir/%.fxs)
XSLS = $(wildcard xsl/*.xsl)

fxs:	$(FXS)

xsls: $(XSLS:xsl/%.xsl=../load-dir/%.xsl)

../load-dir/%.xsl:	xsl/%.xsl
	cp $< $@

py:
	PYTHONPATH=../python/_namespaces:$$PYTHONPATH python ../python/action/action.py

../load-dir/%.fxs:	yang/%.yang
	$(NCSC)  `ls $*-ann.yang  > /dev/null 2>&1 && echo "-a $*-ann.yang"` \
             $(YANGPATH) -c -o $@ $<
	$(NCSC) --emit-python ../python/_namespaces/$(notdir $(basename $<)).py $@

clean:
	rm -rf  ../load-dir/* ../python/_namespaces/*.py
	rm -rf  ./src/*/*.pyc
