#!/usr/bin/env perl

# this filter expands some convenience macros for Poly/ML

use lib ($ENV{RLWRAP_FILTERDIR} or ".");
use RlwrapFilter;
use strict;

my $last_raw_input;
my $filter = new RlwrapFilter;
my $name = $filter -> name;
$filter -> input_handler(\&expand_poly_macros);
$filter -> echo_handler(sub {$last_raw_input}); 
$filter -> run;

sub expand_poly_macros {
	my ($unexpanded) = @_;
	my $expanded = $last_raw_input = $unexpanded;
  	$expanded =~ s/\?s(.*)/"signature SIG = $1;"/e;
  	$expanded =~ s/\?S(.*)/"structure Str = $1;"/e;
	return $expanded;
}
