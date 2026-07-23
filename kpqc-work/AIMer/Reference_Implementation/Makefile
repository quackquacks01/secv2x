# SPDX-License-Identifier: MIT
# ------------------------------------------------------------
# Parameter list (used only in the top‑level make)
# ------------------------------------------------------------
PARAMS_LIST = 128f 128s 192f 192s 256f 256s

# ------------------------------------------------------------
# Top‑level targets
# ------------------------------------------------------------
ifneq ($(SUBMAKE),1)                   # ---------- top level ----------
.PHONY: all $(PARAMS_LIST) clean
all: $(PARAMS_LIST)                    # build all parameter sets

# Re‑invoke make for each parameter, providing its own obj/ and build/
$(PARAMS_LIST):
	@$(MAKE) SUBMAKE=1 PARAMS=$@ OBJDIR=obj/$@ BUILD_DIR=build/$@ all_inner

# Clean everything
clean:
	@echo "=== Removing obj/ and build/ directories ==="
	@rm -rf obj build
	@rm -f *.d PQCsignKAT_*.rsp PQCsignKAT_*.req
	@echo "Clean complete."
else                                   # ---------- recursive make ----------
# ------------------------------------------------------------
# Common settings (inherited from the top level)
# ------------------------------------------------------------
CC      ?= gcc                         # use clang via: make CC=clang
CFLAGS  += -I. -O3 -Wall -Wextra -march=native \
           -fomit-frame-pointer -DPARAMS=$(PARAMS)

# ------------------------------------------------------------
# Executable base names (suffix added later)
# ------------------------------------------------------------
BASE_TESTSIGN = test_sign
BASE_KAT      = PQCgenKAT_sign

# Final executable names: build/<param>/<base>_<param>
EXE_TESTSIGN = $(BUILD_DIR)/$(BASE_TESTSIGN)_$(PARAMS)
EXE_KAT      = $(BUILD_DIR)/$(BASE_KAT)_$(PARAMS)
ALL_EXES     = $(EXE_TESTSIGN) $(EXE_KAT)

# ------------------------------------------------------------
# Source files
# ------------------------------------------------------------
COMMON_SRC = common/aes.c common/fips202.c common/rng.c

HEADERS    = aim2_constant.h aim2.h api.h field.h hash.h \
             params.h sign.h tree.h

SOURCES    = aim2.c hash.c sign.c tree.c
ifneq (,$(findstring 128,$(PARAMS)))
    SOURCES += field128.c
endif
ifneq (,$(findstring 192,$(PARAMS)))
    SOURCES += field192.c
endif
ifneq (,$(findstring 256,$(PARAMS)))
    SOURCES += field256.c
endif

# ------------------------------------------------------------
# Object file lists (stored under obj/<param>/)
# ------------------------------------------------------------
SRC_OBJS = $(patsubst %.c,$(OBJDIR)/%.o,$(SOURCES) $(COMMON_SRC))

# Test sources become obj/<param>/test_<name>.o
TESTS     = $(BASE_TESTSIGN) $(BASE_KAT)
TEST_SRCS = $(addprefix test/,$(addsuffix .c,$(TESTS)))
TEST_OBJS = $(patsubst test/%.c,$(OBJDIR)/test_%.o,$(TEST_SRCS))

# ------------------------------------------------------------
# Main target (build all executables for the current PARAMS)
# ------------------------------------------------------------
.PHONY: all_inner
all_inner: $(ALL_EXES)

# ------------------------------------------------------------
# Compile rules
# ------------------------------------------------------------
$(OBJDIR)/%.o: %.c $(HEADERS)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(OBJDIR)/test_%.o: test/%.c $(HEADERS)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

# Ensure the build/<param>/ directory exists before linking
$(BUILD_DIR):
	@mkdir -p $@

# ------------------------------------------------------------
# Link rules (executables placed in build/<param>/)
# ------------------------------------------------------------
$(EXE_TESTSIGN): $(OBJDIR)/test_$(BASE_TESTSIGN).o $(SRC_OBJS) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ -o $@

$(EXE_KAT): $(OBJDIR)/test_$(BASE_KAT).o $(SRC_OBJS) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ -o $@

# ------------------------------------------------------------
# Optional clean for a single parameter build
# ------------------------------------------------------------
.PHONY: clean_inner
clean_inner:
	@echo "Cleaning build for $(PARAMS) ..."
	@rm -rf $(OBJDIR) $(BUILD_DIR)
	@echo "Clean for $(PARAMS) done."
endif    # ---------- end of SUBMAKE conditional ----------
