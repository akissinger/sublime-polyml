#!/usr/bin/env perl

# This filter expands some convenience macros for Poly/ML and adds very
# rudimentary completion for globals. To use from console, add something
# like this to your .profile:
#
# alias ipoly='rlwrap -z /path/to/poly_filter.pl poly'

use lib ($ENV{RLWRAP_FILTERDIR} or ".");
use RlwrapFilter;
use strict;

my $last_raw_input;
my $filter = new RlwrapFilter;
my $name = $filter -> name;
$filter -> input_handler(\&expand_poly_macros);
$filter -> echo_handler(sub {$last_raw_input});
$filter -> completion_handler(\&complete);
$filter -> run;

sub expand_poly_macros {
	my ($unexpanded) = @_;
	my $expanded = $last_raw_input = $unexpanded;
  	$expanded =~ s/\?s(.*)/"signature SIG__ = $1;"/e;
  	$expanded =~ s/\?S(.*)/"structure Str__ = $1;"/e;
    $expanded =~ s/\?t(.*)/"PolyML.exception_trace (fn() => ( $1 ));"/e;
	return $expanded;
}

sub complete {
  my ($line, $word, @compl) = @_;
  my $kw = $filter -> cloak_and_dagger(
      "val _ = List.foldr (fn (x,_) => TextIO.print (x^\"\\n\")) () (PolyML.Compiler.signatureNames ());",
      "> ", 200);
  $kw .= $filter -> cloak_and_dagger(
      "val _ = List.foldr (fn (x,_) => TextIO.print (x^\"\\n\")) () (PolyML.Compiler.structureNames ());",
      "> ", 200);
  $kw .= $filter -> cloak_and_dagger(
      "val _ = List.foldr (fn (x,_) => TextIO.print (x^\"\\n\")) () (PolyML.Compiler.valueNames ());",
      "> ", 200);
  $kw .= $filter -> cloak_and_dagger(
      "val _ = List.foldr (fn (x,_) => TextIO.print (x^\"\\n\")) () (PolyML.Compiler.typeNames ());",
      "> ", 200);
  
  while ($kw =~ m/(($word).*)/g) {
    my $c = $1;
    $c =~ s/\r//g;;
    push(@compl, $c);
  }
  return @compl;
}

