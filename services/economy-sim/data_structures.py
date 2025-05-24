import enum

class Profession(enum.Enum):
    UNEMPLOYED = "unemployed"
    MINER = "miner"
    LUMBERJACK = "lumberjack"
    FARMER = "farmer"
    FISHER = "fisher"
    CARPENTER = "carpenter"
    BLACKSMITH = "blacksmith"
    JEWELER = "jeweler"
    BAKER = "baker"
    BREWER = "brewer"
    COOK = "cook"
    TAILOR = "tailor"
    TREASURY_OFFICER = "treasury_officer"
    GLADIATOR = "gladiator"
    HAULER = "hauler"   # for logistics

class SkillLevel(enum.Enum):
    NONE = 0
    LOW = 1
    HIGH = 2

SILVER_PER_GOLD = 100

DAILY_WAGES = {
    SkillLevel.NONE: 0,
    SkillLevel.LOW: 6,
    SkillLevel.HIGH: 9
}

GLADIATOR_PRIZE_DISTRIBUTION = {
    1: 23.0, 2: 14.5, 3: 10.0, 4: 7.5, 5: 6.0, 6: 4.5, 7: 3.5, 8: 3.0,
    9: 2.5, 10: 2.0, 11: 2.0, 12: 2.0, 13: 1.5, 14: 1.5, 15: 1.5, 16: 1.2,
    17: 1.2, 18: 1.2, 19: 1.2, 20: 1.2, 21: 1.0, 22: 1.0, 23: 1.0, 24: 1.0,
    25: 1.0, 26: 0.8, 27: 0.8, 28: 0.8, 29: 0.8, 30: 0.8
}

TRAINING_TIME_MONTHS = {
    Profession.MINER: 1,
    Profession.LUMBERJACK: 1,
    Profession.FARMER: 2,
    Profession.FISHER: 1,
    Profession.CARPENTER: 6,
    Profession.BLACKSMITH: 12,
    Profession.JEWELER: 12,
    Profession.BAKER: 2,
    Profession.BREWER: 2,
    Profession.COOK: 2,
    Profession.TAILOR: 8,
    Profession.TREASURY_OFFICER: 12,
    Profession.HAULER: 1
}

SEASONAL_FARM_YIELD = {
    "spring": 0.2,
    "summer": 0.8,
    "fall": 0.9,
    "winter": 0.05
}
