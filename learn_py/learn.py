import asyncio
import aiohttp
from abc import ABC, abstractmethod

class Person(ABC):
    @abstractmethod
    def get_age(self):
        pass

class Animal(Person):
    def get_age(self):
        print("xxx")

    def get_name(self):
        print("name")
    


if __name__ == '__main__':
    p = Animal()
    p.get_name()
    



