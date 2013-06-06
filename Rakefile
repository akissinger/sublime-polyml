task :default => ['vim-polyml.zip']

file 'vim-polyml.zip' => (['sml_polyml.vim','poly']) do |t|
  vimsubdir = 'ftplugin'
  mkdir vimsubdir
  cp_r t.prerequisites, vimsubdir
  system('zip', '-r', '-x*.pyc', t.name, vimsubdir)
  rm_r vimsubdir
end

task :clean => [] do
  rm_f 'vim-polyml.zip'
end
