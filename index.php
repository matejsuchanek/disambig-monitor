<?php

header( 'Content-Type: text/html; charset=utf-8' );
ini_set( 'default_charset', 'utf-8' );
//ini_set( 'display_errors', 1 );
//error_reporting( E_ALL );

function get_value( $value, $fallback = '' ) {
	return !empty( $_GET[$value] ) ? $_GET[$value] : $fallback;
}

function getDBs() {
	$ts_pw = posix_getpwuid( posix_getuid() );
	$ts_mycnf = parse_ini_file( $ts_pw['dir'] . '/replica.my.cnf' );
	$db = mysql_connect( 'tools.db.svc.eqiad.wmflabs', $ts_mycnf['user'], $ts_mycnf['password'] );
	$wd = mysql_connect( 'wikidatawiki.analytics.db.svc.eqiad.wmflabs', $ts_mycnf['user'], $ts_mycnf['password'] );
	mysql_select_db( $ts_mycnf['user'] . '__data', $db );
	mysql_select_db( 'wikidatawiki_p', $wd );
	mysql_set_charset( 'utf8', $db );
	return [ $db, $wd ];
}

$cache = [];

function formatPage( $wiki, $page, $db ) {
	global $cache;
	if ( !isset( $cache[$wiki] ) ) {
		$query = "SELECT site_data FROM sites WHERE site_global_key = '$wiki'";
		$result = mysql_query( $query, $db );
		$row = mysql_fetch_object( $result );
		$data = unserialize( $row->site_data );
		$cache[$wiki] = $data['paths']['page_path'];
	}
	$url = str_replace( '$1', rawurlencode( $page ), $cache[$wiki] );
	return "<a href=\"$url\">" . htmlspecialchars( $page, ENT_NOQUOTES, 'UTF-8' ) . '</a>';
}

function formatUser( $user ) {
	$url_user = rawurlencode( $user );
	$text_user = htmlspecialchars( $user, ENT_NOQUOTES, 'UTF-8' );
	return "<a href=\"//www.wikidata.org/wiki/User:$url_user\">$text_user</a>";
}

function formatItem( $item ) {
	return "<a href=\"//www.wikidata.org/wiki/$item\">$item</a>";
}

$wiki = get_value( 'wiki' );
$field = 'id'; //get_value( 'field', 'id' );
$status = get_value( 'status', [] );
$from = get_value( 'from' );
$dir = get_value( 'dir' ) === 'prev' ? 'prev' : '';
$order = get_value( 'order' ) === 'DESC' ? 'DESC' : 'ASC';
$limit = get_value( 'limit', 50 );

?>
<!doctype html>

<html>

<head>

<title>Disambiguations monitor</title>

<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

</head>

<body>

<p>Use the following form to get a list of problematic links to Wikidata disambiguation items.</p>

<form action="index.php" method="get">

<input type="hidden" name="view" value="1">

<p><label for="wiki">Wiki:</label> <input type="text" id="wiki" name="wiki" value="<?php echo $wiki; ?>"></p>

<p>I want to see:</p>

<p>
<?php

$status_map = [
	'READY' => 'articles',
	'REDIRECT' => 'redirects',
	'DELETED' => 'deleted pages',
	'FALSE' => 'false positives',
];

foreach ( $status_map as $key => $value ) {

	echo "<input type=\"checkbox\" name=\"status[]\" id=\"$key\" value=\"$key\"";
	echo in_array( $key, $status ) ? ' checked="checked"' : '';
	echo ">&nbsp;<label for=\"$key\">$value</label>&nbsp;\n";

}

?>
</p>

<p>Order:
<?php

$order_map = [
	'ASC' => 'ascending',
	'DESC' => 'descending',
];

foreach ( $order_map as $key => $value ) {

	echo "<input type=\"radio\" name=\"order\" id=\"$key\" value=\"$key\"";
	echo $key === $order ? ' checked="checked"' : '';
	echo ">&nbsp;<label for=\"$key\">$value</label>&nbsp;\n";

}

?>
</p>

<p><label for="limit">Limit:</label> <input type="text" id="limit" name="limit" list="limits" value="<?php echo $limit; ?>"></p>

<datalist id="limits">
    <option value="20">
    <option value="50">
    <option value="100">
    <option value="500">
</datalist>

<input type="submit" value="Get disambiguation items">

</form>

<?php

if ( get_value( 'view' ) ) {

	list( $db, $wd ) = getDBs();

	$query = 'SELECT * FROM disambiguations';
	$where = [];
	if ( $wiki ) {
		$where[] = sprintf( "wiki = '%s'", mysql_real_escape_string( $wiki, $db ) );
	}
	if ( $status ) {
		$callback = function ( $value ) use ( $db ) {
			return '"' . mysql_real_escape_string( $value, $db ) . '"';
		};
		$where[] = 'status IN ( ' . implode( ', ', array_map( $callback, $status ) ) . ' )';
	}
	if ( $from ) {
		$op = $dir === 'prev' ? '>' : '<=';
		$where[] = sprintf( "id $op '%d'", $from );
	}
	if ( $where ) {
		$query .= ' WHERE ' . implode( ' AND ', $where );
	}
	$query .= " ORDER BY $field $order";
	$query .= sprintf( ' LIMIT %d', $limit + 1 );

	$result = mysql_query( $query, $db );
	if ( $result ) {

		echo "<br><br>\n";

		$table  = "<table id='main_table'>\n";
		$table .= "<tr><th>Wiki</th><th>Item</th><th>Page</th><th>Status</th><th>Update</th><th>User</th></tr>\n";

		$first = $last = null;

		for ( $i = 0; $i < $limit; ++$i ) {
			$row = mysql_fetch_object( $result );
			if ( !$row ) {
				break;
			}
			if ( !$first ) {
				$first = $row;
			}
			$table .= "<tr>";
			$table .= '<td>' . $row->wiki. '</td>';
			$table .= '<td>' . formatItem( $row->item ) . '</td>';
			$table .= '<td>' . formatPage( $row->wiki, $row->page, $wd ) . '</td>';
			$table .= '<td>' . $row->status . '</td>';
			$table .= '<td>' . $row->stamp . '</td>';
			$table .= '<td>' . formatUser( $row->author ) . '</td>';
			$table .= "</tr>\n";
			$last = $row;
		}

		$links = [];

		$data = compact( 'wiki', 'status', 'order', 'limit' );
		$data['view'] = 1;
		if ( $from ) {
			$query = $data;
			$query['from'] = $first ? $first->id : '';
			$query['dir'] = 'prev';
			$link = '<a href="' . $_SERVER['PHP_SELF'] . '?';
			$link .= http_build_query( $query ) . '">&larr; prev</a>';
			$links[] = $link;
		}

		$next = mysql_fetch_object( $result );
		if ( $next || $dir === 'prev' ) {
			$query = $data;
			$query['from'] = $next ? $next->id : ( $last ? ( $last->id + 1 ) : '' );
			$link = '<a href="' . $_SERVER['PHP_SELF'] . '?';
			$link .= http_build_query( $query ) . '">next &rarr;</a>';
			$links[] = $link;
		}

		$table .= "</table>\n";

		echo implode( '&nbsp;', $links ) . "\n";
		echo $table;
		echo implode( '&nbsp;', $links ) . "\n";

	}

	mysql_close( $db );

}

?>

</body>

</html>