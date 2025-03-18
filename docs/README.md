# Docs

This directory contains [hugo](https://gohugo.io) documentation to be published in Github pages.

## Dependencies

- [Geekdocs v1.5.0](https://github.com/thegeeklab/hugo-geekdoc/releases/tag/v1.5.0)
- [Hugo v0.145.0](https://github.com/gohugoio/hugo/releases/tag/v0.145.0)

## Run Locally

To serve the documentation locally, run the following command:

```shell
hugo server -D
```

This will serve the docs on [http://localhost:1313](http://localhost:1313).

## Update Geekdocs

The docs use the [Geekdocs](https://geekdocs.de/) theme. The theme is checked in to Github in the `./docs/themes/hugo-geekdoc/` folder. To update [Geekdocs](https://geekdocs.de/), remove the current folder and create a new one with the latest [release](https://github.com/thegeeklab/hugo-geekdoc/releases). There are no local modifications in `./docs/themes/hugo-geekdoc/`.

```shell
rm -rf ./docs/themes/hugo-geekdoc
mkdir -p themes/hugo-geekdoc/
curl -L https://github.com/thegeeklab/hugo-geekdoc/releases/latest/download/hugo-geekdoc.tar.gz | tar -xz -C themes/hugo-geekdoc/ --strip-components=1
```

## Deploy to Github Pages

Changes to the `master` branch will be deployed automatically with Github actions.
