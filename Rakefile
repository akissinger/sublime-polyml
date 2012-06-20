$LIB_FILES = Dir[ 'poly/*.py', 'poly/*.pl']

task :default => ['vim-polyml.zip']

file 'vim-polyml.zip' => (['sml_polyml.vim']+$LIB_FILES) do |t|
  command = ['zip', t.name] + t.prerequisites
  system(*command)
end

task :clean => [] do
  rm_f 'vim-polyml.zip'
end
