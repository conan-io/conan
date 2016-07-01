from conans.errors import ConanException

class Target:
    data = {}
    def __init__(self, name, parents = []):
        self.name = name;
        self.parents = []
        for p in parents:
                self.parents += [Target.data[p]]
        Target.data[self.name] = self
    def groups(self):
        ret = [self.name]
        for p in self.parents:
            ret += p.groups()
        return ret
    
class Board(Target):
    data = {}
    def __init__(self, name, microcontroller, parents = []):
        Target.__init__(self, name, parents)
        self.microcontroller = Target.data[microcontroller]
        Board.data[self.name] = self
    def groups(self):
        ret = Target.groups(self)
        ret += self.microcontroller.groups()
        return ret
        
class MCU(Target):
    data = {}
    def __init__(self, name, parents = []):
        Target.__init__(self, name, parents)
        MCU.data[self.name] = self

class Embedded:
    Target("avr")
    Target("atmega", ["avr"])
    Target("atmegaxx0_1", ["atmega"])
    Target("atmegax8", ["atmega"])

    Target("arm")
    Target("cortex_m4", ["arm"])
    
    Target("stm32", ["arm"])
    Target("stm32f4", ["stm32", "cortex_m4"])

    MCU("atmega2560", ["atmegaxx0_1"])
    MCU("atmega328p", ["atmegax8"])
    MCU("stm32f407vg", ["stm32f4"])

    Target("discovery")
    Target("arduino")
    
    Board("arduino_mega", "atmega2560", ["arduino"])
    Board("arduino_uno", "atmega328p", ["arduino"])
    Board("stm32f4_discovery", "stm32f407vg", ["discovery"])

    def __init__(self, settings):
        self.target = None
        self.mcu = None
        if settings.target == "mcu":
            self.target = MCU.data[str(settings.target.mcu)]
            self.mcu = self.target
        elif settings.target == "board":
            self.target = Board.data[str(settings.target.board)]
            self.mcu = self.target.microcontroller
        else:
            raise ConanException("Invalid target : " + str(settings.target))

    def name(self):
        return self.target.name

    def microcontroller(self):
        return self.mcu.name

    def groups(self):
        return self.target.groups()
