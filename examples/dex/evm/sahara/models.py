from pydantic import BaseModel


class Question(BaseModel):
    question: str


class TextQuestion(Question):
    min_length: int
    max_length: int

    def __repr__(self):
        return f'{self.question} Answer in {self.min_length}-{self.max_length} characters'

    def __str__(self):
        return self.__repr__()


class SingleChoiceQuestion(Question):
    options: list[str]

    def __repr__(self):
        return f'{self.question}\n' + '\n'.join(self.options)

    def __str__(self):
        return self.__repr__()
