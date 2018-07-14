CREATE TABLE disambiguations (
	id int NOT NULL AUTO_INCREMENT,
	item char(10) NOT NULL,
	wiki char(32) NOT NULL,
	page varchar(255) NOT NULL,
	stamp timestamp NOT NULL,
	status ENUM('READY', 'DELETED', 'REDIRECT', 'FALSE') NOT NULL,
	author varchar(255) NOT NULL,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX wiki_item ON disambiguations (wiki, item);
--CREATE UNIQUE INDEX wiki_page ON disambiguations (wiki, page);