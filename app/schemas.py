from pydantic import BaseModel, Field


class BotScheme(BaseModel):
	id: int = Field(default=None)
	balance: int
	token: str
	active: bool
	nickname: str

	class Meta:
		orm_mode = True