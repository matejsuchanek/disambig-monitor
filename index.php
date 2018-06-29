<?php

function get_value( $value, $fallback = '' ) {
	return isset( $_GET[$value] ) ? $_GET[$value] : $fallback;
}

function getDB() {
	$ts_pw = posix_getpwuid( posix_getuid() );
	$ts_mycnf = parse_ini_file( $ts_pw['dir'] . '/replica.my.cnf' );
	$db = mysql_connect( 'tools.db.svc.eqiad.wmflabs', $ts_mycnf['user'], $ts_mycnf['password'] );
	mysql_select_db( $ts_mycnf['user'] . '__data', $db );
	return $db;
}

$wiki = get_value( 'wiki' );
$key = get_value( 'key', 'id' );
$order = get_value( 'desc' ) ? 'DESC' : 'ASC';
$limit = get_value( 'limit', 50 );

?>
<!doctype html>

<html>

<head>

<title>Disambiguations monitor</title>

</head>

<body>

<p>Use the following form to ...</p>

<form action="index.php" method="get">

<input type="hidden" name="view" value="1">

<p>Wiki: <input type="text" name="wiki" value="<?php echo $wiki; ?>"></p>

<!--p>Sort by:</p-->

<p>Limit: <input type="text" name="limit" list="limit" value="<?php echo $limit; ?>"></p>

<datalist id="limit">
    <option value="20">
    <option value="50">
    <option value="100">
    <option value="500">
</datalist>

<p><button name="submit" type="submit" value="Get disambiguation items" /></p>

</form>

<?php

if ( get_value( 'view' ) ) {

	$db = getDB();

	$query = 'SELECT * FROM disambiguations';
	$conds = [];
	if ( $wiki ) {
		$conds[] = sprintf( "wiki = '%s'", mysql_real_escape_string( $wiki, $db ) );
	}
	if ( $conds ) {
		$query .= ' WHERE ' . implode( 'AND', $conds );
	}
	$query .= " ORDER BY $key $order";
	$query .= sprintf( ' LIMIT %d', $limit + 1 );

	$result = mysql_query( $query, $db );
	if ( $result ) {

		echo "<table id='main_table'>\n";
		echo "<tr><th>Wiki</th><th>Page</th><th>Status</th><th>Update</th><th>User</th></tr>\n";

		for ( $i = 0; $i < $limit; ++$i ) {
			$row = mysql_fetch_object( $result );
			if ( !$row ) {
				break;
			}
			echo "<tr>";
			echo "<td>{$row->wiki}</td>";
			echo "<td>{$row->page}</td>";
			echo "<td>{$row->status}</td>";
			echo "<td>{$row->stamp}</td>";
			echo "<td>{$row->author}</td>";
			echo "</tr>\n";
		}

		$next = mysql_fetch_object( $result );
		if ( $next ) {
			// TODO
		}

		echo "</table>\n";

	}

	mysql_close( $db );

}

?>

</body>

</html>