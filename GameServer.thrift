namespace py Services

service GameService
{
	void update(1:i16 source, 2:i16 target, 3:i16 action, 4:i16 data),
	void message(1:i16 source, 2:i16 target, 3:string message),
	void initGame(1:i16 gameMode),
}

service GamePlayer
{
        i32 discover(1:string serverName, 2:string serverIP),
	string getName(),
	i32 readID(),
        i32 getTeam(),
	void startGame(1:string server, 2:i16 gameMode, 3:i16 playerID, 4:i16 teamMask),
	void message(1:i16 source, 2:string message),
	void fire(),
	void hit(1:i16 source, 2:i16 weapon),
        void die(),
        void revive(),
	void endGame(),
}
