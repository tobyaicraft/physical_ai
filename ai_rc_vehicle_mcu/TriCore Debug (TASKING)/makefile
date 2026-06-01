################################################################################
# Automatically-generated file. Do not edit!
################################################################################

-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include Libraries/iLLD/TC23A/Tricore/_PinMap/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/_Lib/DataHandling/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/_Impl/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Vadc/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Vadc/Adc/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Stm/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Src/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Scu/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Qspi/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Qspi/SpiMaster/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Port/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Gtm/Tom/Timer/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Gtm/Tom/Pwm/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Gtm/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Flash/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Dma/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Dma/Dma/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Cpu/Trap/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Cpu/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Cpu/Irq/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Cpu/CStart/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Asclin/Std/subdir.mk
-include Libraries/iLLD/TC23A/Tricore/Asclin/Asc/subdir.mk
-include Libraries/Service/CpuGeneric/StdIf/subdir.mk
-include Libraries/Infra/Platform/Tricore/Compilers/subdir.mk
-include Configurations/Debug/subdir.mk
-include subdir.mk
ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(C++M_DEPS)),)
-include $(C++M_DEPS)
endif
ifneq ($(strip $(C++_DEPS)),)
-include $(C++_DEPS)
endif
ifneq ($(strip $(CCM_DEPS)),)
-include $(CCM_DEPS)
endif
ifneq ($(strip $(CC_DEPS)),)
-include $(CC_DEPS)
endif
ifneq ($(strip $(CPP_DEPS)),)
-include $(CPP_DEPS)
endif
ifneq ($(strip $(CXXM_DEPS)),)
-include $(CXXM_DEPS)
endif
ifneq ($(strip $(CXX_DEPS)),)
-include $(CXX_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
ifneq ($(strip $(C_UPPER_DEPS)),)
-include $(C_UPPER_DEPS)
endif
endif

-include ../makefile.defs

OPTIONAL_TOOL_DEPS := \
$(wildcard ../makefile.defs) \
$(wildcard ../makefile.init) \
$(wildcard ../makefile.targets) \


BUILD_ARTIFACT_NAME := ai_rc_vehicle_mcu
BUILD_ARTIFACT_EXTENSION := elf
BUILD_ARTIFACT_PREFIX :=
BUILD_ARTIFACT := $(BUILD_ARTIFACT_PREFIX)$(BUILD_ARTIFACT_NAME)$(if $(BUILD_ARTIFACT_EXTENSION),.$(BUILD_ARTIFACT_EXTENSION),)

# Add inputs and outputs from these tool invocations to the build variables 
SECONDARY_SIZE += \
ai_rc_vehicle_mcu.siz \


# All Target
all: main-build

# Main-build Target
main-build: ai_rc_vehicle_mcu.elf secondary-outputs

# Tool invocations
ai_rc_vehicle_mcu.elf: $(OBJS) makefile $(OPTIONAL_TOOL_DEPS) .ai_rc_vehicle_mcu.elf.opt
	@echo 'Building target: $@'
	@echo 'Invoking: TASKING Linker'
	cctc -f .ai_rc_vehicle_mcu.elf.opt
	@echo 'Finished building target: $@'
	@echo ' '

.ai_rc_vehicle_mcu.elf.opt:
	@argfile .ai_rc_vehicle_mcu.elf.opt --lsl-file="../Lcf_Tasking_Tricore_Tc.lsl" -Wl-Oc -Wl-OL -Wl-Ot -Wl-Ox -Wl-Oy -Wl--map-file="ai_rc_vehicle_mcu.map" -Wl-mc -Wl-mf -Wl-mi -Wl-mk -Wl-ml -Wl-mm -Wl-md -Wl-mr -Wl-mu --no-warnings= -Wl--error-limit=42 --fp-model=3 -lrt --lsl-core=vtc --exceptions --strict --anachronisms --force-c++ -Ctc23x -o"ai_rc_vehicle_mcu.elf" -Wl-o"ai_rc_vehicle_mcu.hex:IHEX" $(OBJS)

.PHONY: .ai_rc_vehicle_mcu.elf.opt

ai_rc_vehicle_mcu.siz: ai_rc_vehicle_mcu.elf makefile $(OPTIONAL_TOOL_DEPS)
	@echo 'Invoking: Print Size'
	elfsize  "ai_rc_vehicle_mcu.elf"
	@echo 'Finished building: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) ai_rc_vehicle_mcu.siz ai_rc_vehicle_mcu.elf
	-@echo ' '

secondary-outputs: $(SECONDARY_SIZE)

.PHONY: all clean dependents main-build

-include ../makefile.targets
