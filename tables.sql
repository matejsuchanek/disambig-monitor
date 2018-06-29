CREATE TABLE disambiguations (
	id int NOT NULL AUTO_INCREMENT,
	item char(10) NOT NULL,
	wiki char(13) NOT NULL,
	page varchar(255) NOT NULL,
	stamp timestamp NOT NULL,
	status ENUM('READY', 'DELETED', 'REDIRECT', 'FALSE') NOT NULL,
	author varchar(255) NOT NULL,
	PRIMARY KEY (id)
);

CREATE INDEX wiki ON disambiguations (wiki);
--CREATE UNIQUE INDEX wiki_page ON disambiguations (wiki, page);
--CREATE UNIQUE INDEX wiki_item ON disambiguations (item, wiki);