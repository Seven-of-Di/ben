import click
from play_card import PlayCardTest

@click.command()
@click.option('--threads', default=1, help='Number of parallel threads to run the load from', type=int)
@click.option('--count', help='Total count of requests to make', type=int)
@click.option('--url', help='The URL to execute the test agaist')
def play_card(threads, count, url):
    PlayCardTest(threads=threads, count=count, url=url).execute()

if __name__ == '__main__':
    play_card()
