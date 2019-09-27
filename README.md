# Skinifi: Thinner NiFi Images for Docker

## About
Skinifi (skinny-nifi) is a python tool for creating NiFi images without unneeded artifacts or documentation.

NiFi's default image is currently a couple Gigabytes in size, largely due to the trove of useful libraries. However, 
this becomes a problem in environments where space is limited or when images are frequently moved around. 
While MiNiFi is a helpful alternative, it is sometimes preferable to have access to NiFi's workspace.

A skinifi image by default is only 600 MB and contains only the artifacts needed to run. This tool also allows you
to specify the Process Groups you need to use and imports the processors needed for them to run.

## How to Use
If you want to create the base skinifi image without extra artifacts, run `python3 create_skinifi.py`

The image will be created and added to your local docker environment with the name **skinifi** (use --tag to customize)

Adding addtional artifacts to skinifi can be done by adding either a template or Flow. `create_skinifi` will parse
these files for artifacts to include into the NiFi image.

### Adding a Template
1. Create a template using an existing NiFi instance. Learn how

2. Save the template as an xml and copy it to **templates/**

3. Running `create_skinifi` will automatically parse xml templates in this directory

### Adding a Flow from NiFi Registry
1. Create a file titled **registries.json** in the root directory (this one)

2. Create a Json object specifying the registry url, bucket id, and the flow id you wish to use. 
    See **registries.json.example** for reference.
    
3. Running `create_skinifi` will automatically parse flows specified in **registries.json**

IMPORTANT: If you are using custom processors in your flow you will need to add the nar file to 
**custom-processors/**. Skinifi is not yet capable of pulling down nar files from NiFi Registry.

### Adding Custom Processors
If you are using custom processors in your work, you will need to add the nar file to 
**custom-processors/** or by specifying a path with the `--custom-nar-directory` flag. Nar files which are specified 
in either a template or Flow will be copied into the skinifi image.

Note: `create_skinifi` does not search **custom-processors** for nar files recursively. Avoid adding subdirectories
to here

### Adding Default Processors
By default, `create_skinifi` will download the required default processors from an online repository. If you want to use
a different path or url, set that with the ` --generic-nar-directory` flag.

Once downloaded, skinifi will save the processors to **skinifi-image/generic-nars/** for future use.